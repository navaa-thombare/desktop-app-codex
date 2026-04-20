from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.auth.dtos import SessionRecord, UserRecord


class InMemoryUserRepository:
    def __init__(
        self,
        users: list[UserRecord],
        recovery_contacts: dict[str, str | tuple[str, ...]] | None = None,
    ) -> None:
        self._users = {user.user_id: user for user in users}
        self._recovery_contacts: dict[str, set[str]] = {}
        for user in users:
            tokens = set()
            if user.mobile:
                tokens.add(self._normalize_contact_value(user.mobile))
            self._recovery_contacts[user.user_id] = {token for token in tokens if token}

        for user_id, values in (recovery_contacts or {}).items():
            contact_values = values if isinstance(values, tuple) else (values,)
            self._recovery_contacts.setdefault(user_id, set()).update(
                {
                    normalized
                    for normalized in (
                        self._normalize_contact_value(value) for value in contact_values
                    )
                    if normalized
                }
            )

    def get_by_username(self, username: str) -> UserRecord | None:
        return next((u for u in self._users.values() if u.username == username), None)

    def get_by_mobile(self, mobile: str) -> UserRecord | None:
        return next((u for u in self._users.values() if u.mobile == mobile), None)

    def get_by_user_id(self, user_id: str) -> UserRecord | None:
        return self._users.get(user_id)

    def matches_recovery_contact(self, *, user_id: str, recovery_contact: str) -> bool:
        normalized_contact = self._normalize_contact_value(recovery_contact)
        if not normalized_contact:
            return False
        return normalized_contact in self._recovery_contacts.get(user_id, set())

    def register_failed_attempt(
        self,
        user_id: str,
        failed_attempts: int,
        lockout_until: datetime | None,
    ) -> None:
        user = self._users[user_id]
        self._users[user_id] = UserRecord(
            user_id=user.user_id,
            username=user.username,
            mobile=user.mobile,
            password_hash=user.password_hash,
            failed_attempts=failed_attempts,
            lockout_until=lockout_until,
            password_reset_required=user.password_reset_required,
        )

    def clear_failed_attempts(self, user_id: str) -> None:
        user = self._users[user_id]
        self._users[user_id] = UserRecord(
            user_id=user.user_id,
            username=user.username,
            mobile=user.mobile,
            password_hash=user.password_hash,
            failed_attempts=0,
            lockout_until=None,
            password_reset_required=user.password_reset_required,
        )

    def update_password(
        self,
        *,
        user_id: str,
        password_hash: str,
        password_reset_required: bool,
    ) -> None:
        user = self._users[user_id]
        self._users[user_id] = UserRecord(
            user_id=user.user_id,
            username=user.username,
            mobile=user.mobile,
            password_hash=password_hash,
            failed_attempts=0,
            lockout_until=None,
            password_reset_required=password_reset_required,
        )

    @staticmethod
    def _normalize_contact_value(value: str | None) -> str:
        if value is None:
            return ""
        return value.strip().lower()


class InMemorySessionRepository:
    def create_session(
        self,
        *,
        user_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> SessionRecord:
        return SessionRecord(
            session_id=secrets.token_urlsafe(24),
            user_id=user_id,
            token=secrets.token_urlsafe(48),
            expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=12),
        )


@dataclass(frozen=True)
class Sha256PasswordVerifier:
    pepper: str

    def verify(self, password_hash: str, plain_password: str) -> bool:
        computed_hash = hash_password(plain_password, pepper=self.pepper)
        return hmac.compare_digest(password_hash, computed_hash)

    def hash(self, plain_password: str) -> str:
        return hash_password(plain_password, pepper=self.pepper)


def hash_password(plain_password: str, *, pepper: str) -> str:
    payload = f"{pepper}:{plain_password}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
