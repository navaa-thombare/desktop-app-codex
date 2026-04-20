from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.auth.dtos import AuthFailureCode, LoginRequest, LoginResult, ThrottlePolicy, UserRecord
from app.auth.repositories import SessionRepository, UserRepository
from app.platform.audit import AuditActor, AuditEventType, AuditService
from app.platform.logging.context import ensure_correlation_id

logger = logging.getLogger(__name__)


class PasswordVerifier(Protocol):
    def verify(self, password_hash: str, plain_password: str) -> bool:
        ...

    def hash(self, plain_password: str) -> str:
        ...


class PasswordResetHook(Protocol):
    def on_password_reset_required(self, user_id: str) -> None:
        ...


class Argon2idPasswordVerifier:
    """Argon2id password verifier using argon2-cffi's high-level hasher."""

    def __init__(self) -> None:
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError
        except ImportError as exc:  # pragma: no cover - import guard only
            raise RuntimeError(
                "argon2-cffi is required for Argon2idPasswordVerifier"
            ) from exc

        self._hasher = PasswordHasher()
        self._verify_mismatch_error = VerifyMismatchError

    def verify(self, password_hash: str, plain_password: str) -> bool:
        try:
            return bool(self._hasher.verify(password_hash, plain_password))
        except self._verify_mismatch_error:
            return False

    def hash(self, plain_password: str) -> str:
        return str(self._hasher.hash(plain_password))


@dataclass
class AuthService:
    user_repository: UserRepository
    session_repository: SessionRepository
    password_verifier: PasswordVerifier
    throttle_policy: ThrottlePolicy = ThrottlePolicy()
    password_reset_hook: PasswordResetHook | None = None
    audit_service: AuditService | None = None

    def login(self, request: LoginRequest) -> LoginResult:
        now = datetime.now(tz=timezone.utc)
        correlation_id = ensure_correlation_id(request.correlation_id)
        user = self._resolve_user(request.identifier)

        if user is None:
            self._publish_login_event(
                event_type=AuditEventType.LOGIN_FAILED,
                correlation_id=correlation_id,
                actor_id=None,
                request=request,
                details={"reason": AuthFailureCode.INVALID_CREDENTIALS.value},
            )
            return LoginResult(success=False, failure_code=AuthFailureCode.INVALID_CREDENTIALS)

        if user.lockout_until and user.lockout_until > now:
            self._publish_login_event(
                event_type=AuditEventType.LOGIN_FAILED,
                correlation_id=correlation_id,
                actor_id=user.user_id,
                request=request,
                details={
                    "reason": AuthFailureCode.LOCKED_OUT.value,
                    "lockout_until": user.lockout_until.isoformat(),
                },
            )
            return LoginResult(
                success=False,
                failure_code=AuthFailureCode.LOCKED_OUT,
                lockout_until=user.lockout_until,
            )

        if not self.password_verifier.verify(user.password_hash, request.password):
            return self._handle_failed_login(user, now, request, correlation_id)

        self.user_repository.clear_failed_attempts(user.user_id)
        session = self.session_repository.create_session(
            user_id=user.user_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
        )

        if user.password_reset_required and self.password_reset_hook:
            self.password_reset_hook.on_password_reset_required(user.user_id)

        self._publish_login_event(
            event_type=AuditEventType.LOGIN_SUCCEEDED,
            correlation_id=correlation_id,
            actor_id=user.user_id,
            request=request,
            details={
                "session_id": session.session_id,
                "password_reset_required": user.password_reset_required,
            },
        )

        return LoginResult(
            success=True,
            session=session,
            password_reset_required=user.password_reset_required,
        )

    def begin_password_recovery(
        self,
        *,
        identifier: str,
        recovery_contact: str,
        correlation_id: str | None = None,
    ) -> "PasswordRecoveryResult":
        normalized_identifier = identifier.strip()
        normalized_contact = recovery_contact.strip()
        if not normalized_identifier or not normalized_contact:
            raise ValueError("Enter the identifier and one registered contact value.")

        correlation = ensure_correlation_id(correlation_id)
        user = self._resolve_user(normalized_identifier)
        if user is None or not self.user_repository.matches_recovery_contact(
            user_id=user.user_id,
            recovery_contact=normalized_contact,
        ):
            self._publish_password_recovery_event(
                correlation_id=correlation,
                actor_id=user.user_id if user else None,
                identifier=normalized_identifier,
                recovery_contact=normalized_contact,
                success=False,
            )
            return PasswordRecoveryResult(success=False)

        self._publish_password_recovery_event(
            correlation_id=correlation,
            actor_id=user.user_id,
            identifier=normalized_identifier,
            recovery_contact=normalized_contact,
            success=True,
        )
        return PasswordRecoveryResult(
            success=True,
            user_id=user.user_id,
            username=user.username,
        )

    def reset_password(self, *, user_id: str, new_password: str) -> None:
        user = self.user_repository.get_by_user_id(user_id)
        if user is None:
            raise ValueError("Unknown user account.")

        candidate = new_password.strip()
        self._validate_password(candidate)
        if self.password_verifier.verify(user.password_hash, candidate):
            raise ValueError("New password must be different from the current temporary password.")

        self.user_repository.update_password(
            user_id=user_id,
            password_hash=self.password_verifier.hash(candidate),
            password_reset_required=False,
        )

        if self.audit_service is not None:
            self.audit_service.publish(
                event_type=AuditEventType.ADMIN_CHANGE,
                correlation_id=ensure_correlation_id(),
                actor=AuditActor(actor_id=user_id),
                payload={"action": "reset_password", "target_type": "auth_user", "value": user_id},
            )

    def _resolve_user(self, identifier: str) -> UserRecord | None:
        username_match = self.user_repository.get_by_username(identifier)
        if username_match:
            return username_match
        return self.user_repository.get_by_mobile(identifier)

    def _handle_failed_login(
        self,
        user: UserRecord,
        now: datetime,
        request: LoginRequest,
        correlation_id: str,
    ) -> LoginResult:
        failed_attempts = user.failed_attempts + 1
        lockout_until = None

        if failed_attempts >= self.throttle_policy.max_attempts:
            lockout_until = now + timedelta(seconds=self.throttle_policy.lockout_seconds)

        self.user_repository.register_failed_attempt(
            user.user_id,
            failed_attempts=failed_attempts,
            lockout_until=lockout_until,
        )

        failure_code = (
            AuthFailureCode.LOCKED_OUT
            if lockout_until is not None
            else AuthFailureCode.INVALID_CREDENTIALS
        )
        self._publish_login_event(
            event_type=AuditEventType.LOGIN_FAILED,
            correlation_id=correlation_id,
            actor_id=user.user_id,
            request=request,
            details={
                "reason": failure_code.value,
                "failed_attempts": failed_attempts,
                "lockout_until": lockout_until.isoformat() if lockout_until else None,
            },
        )
        return LoginResult(
            success=False,
            failure_code=failure_code,
            lockout_until=lockout_until,
        )

    def _publish_login_event(
        self,
        *,
        event_type: AuditEventType,
        correlation_id: str,
        actor_id: str | None,
        request: LoginRequest,
        details: dict[str, object],
    ) -> None:
        payload = {
            "identifier_masked": self._mask_value(request.identifier),
            "ip_address": request.ip_address,
            "user_agent": request.user_agent,
            **details,
        }
        logger.info(
            "authentication_attempt",
            extra={
                "event_type": event_type.value,
                "actor_id": actor_id,
                "correlation_id": correlation_id,
                "auth_payload": payload,
            },
        )
        if self.audit_service is not None:
            self.audit_service.publish(
                event_type=event_type,
                correlation_id=correlation_id,
                actor=AuditActor(actor_id=actor_id),
                payload=payload,
            )

    def _publish_password_recovery_event(
        self,
        *,
        correlation_id: str,
        actor_id: str | None,
        identifier: str,
        recovery_contact: str,
        success: bool,
    ) -> None:
        if self.audit_service is None:
            return

        self.audit_service.publish(
            event_type=AuditEventType.ADMIN_CHANGE,
            correlation_id=correlation_id,
            actor=AuditActor(actor_id=actor_id),
            payload={
                "action": "password_recovery_verified" if success else "password_recovery_rejected",
                "identifier_masked": self._mask_value(identifier),
                "recovery_contact_masked": self._mask_value(recovery_contact),
            },
        )

    def _validate_password(self, candidate: str) -> None:
        if len(candidate) < 12:
            raise ValueError("New password must be at least 12 characters long.")
        if not any(character.isupper() for character in candidate):
            raise ValueError("New password must contain at least one uppercase letter.")
        if not any(character.islower() for character in candidate):
            raise ValueError("New password must contain at least one lowercase letter.")
        if not any(character.isdigit() for character in candidate):
            raise ValueError("New password must contain at least one digit.")
        if not any(not character.isalnum() for character in candidate):
            raise ValueError("New password must contain at least one special character.")

    @staticmethod
    def _mask_value(value: str) -> str:
        normalized = value.strip()
        if len(normalized) <= 2:
            return "***"
        return normalized[:2] + "***"


@dataclass(frozen=True)
class PasswordRecoveryResult:
    success: bool
    user_id: str | None = None
    username: str | None = None
