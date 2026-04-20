from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.admin.services import ManagedUserAuthModel, ManagedUserModel
from app.auth.dtos import UserRecord


@dataclass(frozen=True)
class SqlUserRepository:
    session_factory: sessionmaker[Session]

    def get_by_username(self, username: str) -> UserRecord | None:
        normalized_username = username.strip().lower()
        with self.session_factory() as session:
            auth_record = session.scalar(
                select(ManagedUserAuthModel)
                .options(joinedload(ManagedUserAuthModel.user))
                .join(ManagedUserModel)
                .where(ManagedUserModel.username == normalized_username)
            )
            return self._to_user_record(auth_record)

    def get_by_mobile(self, mobile: str) -> UserRecord | None:
        normalized_mobile = mobile.strip()
        with self.session_factory() as session:
            auth_record = session.scalar(
                select(ManagedUserAuthModel)
                .options(joinedload(ManagedUserAuthModel.user))
                .where(ManagedUserAuthModel.mobile == normalized_mobile)
            )
            return self._to_user_record(auth_record)

    def get_by_user_id(self, user_id: str) -> UserRecord | None:
        with self.session_factory() as session:
            auth_record = session.scalar(
                select(ManagedUserAuthModel)
                .options(joinedload(ManagedUserAuthModel.user))
                .where(ManagedUserAuthModel.user_id == user_id)
            )
            return self._to_user_record(auth_record)

    def matches_recovery_contact(self, *, user_id: str, recovery_contact: str) -> bool:
        normalized_contact = self._normalize_contact_value(recovery_contact)
        if not normalized_contact:
            return False

        with self.session_factory() as session:
            auth_record = session.scalar(
                select(ManagedUserAuthModel)
                .options(joinedload(ManagedUserAuthModel.user))
                .where(ManagedUserAuthModel.user_id == user_id)
            )
            if auth_record is None or auth_record.user is None:
                return False
            return normalized_contact in self._recovery_contact_tokens(auth_record)

    def register_failed_attempt(
        self,
        user_id: str,
        failed_attempts: int,
        lockout_until: datetime | None,
    ) -> None:
        with self.session_factory() as session:
            auth_record = session.get(ManagedUserAuthModel, user_id)
            if auth_record is None:
                raise ValueError(f"Unknown auth user: {user_id}")

            auth_record.failed_attempts = failed_attempts
            auth_record.lockout_until = lockout_until
            session.commit()

    def clear_failed_attempts(self, user_id: str) -> None:
        with self.session_factory() as session:
            auth_record = session.get(ManagedUserAuthModel, user_id)
            if auth_record is None:
                raise ValueError(f"Unknown auth user: {user_id}")

            auth_record.failed_attempts = 0
            auth_record.lockout_until = None
            session.commit()

    def update_password(
        self,
        *,
        user_id: str,
        password_hash: str,
        password_reset_required: bool,
    ) -> None:
        with self.session_factory() as session:
            auth_record = session.get(ManagedUserAuthModel, user_id)
            if auth_record is None:
                raise ValueError(f"Unknown auth user: {user_id}")

            auth_record.password_hash = password_hash
            auth_record.password_reset_required = password_reset_required
            auth_record.failed_attempts = 0
            auth_record.lockout_until = None
            session.commit()

    def _to_user_record(self, auth_record: ManagedUserAuthModel | None) -> UserRecord | None:
        if auth_record is None or auth_record.user is None:
            return None

        lockout_until = auth_record.lockout_until
        if lockout_until is not None and lockout_until.tzinfo is None:
            lockout_until = lockout_until.replace(tzinfo=timezone.utc)

        return UserRecord(
            user_id=auth_record.user_id,
            username=auth_record.user.username,
            mobile=auth_record.mobile,
            password_hash=auth_record.password_hash,
            failed_attempts=auth_record.failed_attempts,
            lockout_until=lockout_until,
            password_reset_required=auth_record.password_reset_required,
        )

    @staticmethod
    def _normalize_contact_value(value: str | None) -> str:
        if value is None:
            return ""
        return value.strip().lower()

    @classmethod
    def _recovery_contact_tokens(cls, auth_record: ManagedUserAuthModel) -> set[str]:
        tokens = {
            cls._normalize_contact_value(auth_record.user.contact_info),
            cls._normalize_contact_value(auth_record.mobile),
        }
        tokens.update(
            cls._normalize_contact_value(token)
            for token in re.split(r"[|,;/\n]", auth_record.user.contact_info)
        )
        return {token for token in tokens if token}
