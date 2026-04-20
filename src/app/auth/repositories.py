from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.auth.dtos import SessionRecord, UserRecord


class UserRepository(Protocol):
    def get_by_username(self, username: str) -> UserRecord | None:
        ...

    def get_by_mobile(self, mobile: str) -> UserRecord | None:
        ...

    def get_by_user_id(self, user_id: str) -> UserRecord | None:
        ...

    def matches_recovery_contact(self, *, user_id: str, recovery_contact: str) -> bool:
        ...

    def register_failed_attempt(
        self,
        user_id: str,
        failed_attempts: int,
        lockout_until: datetime | None,
    ) -> None:
        ...

    def clear_failed_attempts(self, user_id: str) -> None:
        ...

    def update_password(
        self,
        *,
        user_id: str,
        password_hash: str,
        password_reset_required: bool,
    ) -> None:
        ...


class SessionRepository(Protocol):
    def create_session(
        self,
        *,
        user_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> SessionRecord:
        ...
