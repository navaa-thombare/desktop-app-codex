from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.auth.dtos import SessionRecord, UserRecord


class InMemoryUserRepository:
    def __init__(self, users: list[UserRecord]) -> None:
        self._users = {user.user_id: user for user in users}

    def get_by_username(self, username: str) -> UserRecord | None:
        return next((u for u in self._users.values() if u.username == username), None)

    def get_by_mobile(self, mobile: str) -> UserRecord | None:
        return next((u for u in self._users.values() if u.mobile == mobile), None)

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


def hash_password(plain_password: str, *, pepper: str) -> str:
    payload = f"{pepper}:{plain_password}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
