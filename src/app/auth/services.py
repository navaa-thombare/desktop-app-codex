from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.auth.dtos import AuthFailureCode, LoginRequest, LoginResult, ThrottlePolicy, UserRecord
from app.auth.repositories import SessionRepository, UserRepository


class PasswordVerifier(Protocol):
    def verify(self, password_hash: str, plain_password: str) -> bool:
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


@dataclass
class AuthService:
    user_repository: UserRepository
    session_repository: SessionRepository
    password_verifier: PasswordVerifier
    throttle_policy: ThrottlePolicy = ThrottlePolicy()
    password_reset_hook: PasswordResetHook | None = None

    def login(self, request: LoginRequest) -> LoginResult:
        now = datetime.now(tz=timezone.utc)
        user = self._resolve_user(request.identifier)

        if user is None:
            return LoginResult(success=False, failure_code=AuthFailureCode.INVALID_CREDENTIALS)

        if user.lockout_until and user.lockout_until > now:
            return LoginResult(
                success=False,
                failure_code=AuthFailureCode.LOCKED_OUT,
                lockout_until=user.lockout_until,
            )

        if not self.password_verifier.verify(user.password_hash, request.password):
            return self._handle_failed_login(user, now)

        self.user_repository.clear_failed_attempts(user.user_id)
        session = self.session_repository.create_session(
            user_id=user.user_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
        )

        if user.password_reset_required and self.password_reset_hook:
            self.password_reset_hook.on_password_reset_required(user.user_id)

        return LoginResult(
            success=True,
            session=session,
            password_reset_required=user.password_reset_required,
        )

    def _resolve_user(self, identifier: str) -> UserRecord | None:
        username_match = self.user_repository.get_by_username(identifier)
        if username_match:
            return username_match
        return self.user_repository.get_by_mobile(identifier)

    def _handle_failed_login(self, user: UserRecord, now: datetime) -> LoginResult:
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
        return LoginResult(
            success=False,
            failure_code=failure_code,
            lockout_until=lockout_until,
        )
