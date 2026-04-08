from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.auth.dtos import SessionRecord, UserRecord


class UserRepository(Protocol):
    def get_by_username(self, username: str) -> UserRecord | None:
        ...

    def get_by_mobile(self, mobile: str) -> UserRecord | None:
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


class SessionRepository(Protocol):
    def create_session(
        self,
        *,
        user_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> SessionRecord:
        ...
