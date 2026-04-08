from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.auth.dtos import AuthFailureCode, LoginRequest, SessionRecord, ThrottlePolicy, UserRecord
from app.auth.services import AuthService


class InMemoryUserRepository:
    def __init__(self, users: list[UserRecord]) -> None:
        self.users = {user.user_id: user for user in users}

    def get_by_username(self, username: str) -> UserRecord | None:
        return next((u for u in self.users.values() if u.username == username), None)

    def get_by_mobile(self, mobile: str) -> UserRecord | None:
        return next((u for u in self.users.values() if u.mobile == mobile), None)

    def register_failed_attempt(
        self,
        user_id: str,
        failed_attempts: int,
        lockout_until: datetime | None,
    ) -> None:
        user = self.users[user_id]
        self.users[user_id] = UserRecord(
            user_id=user.user_id,
            username=user.username,
            mobile=user.mobile,
            password_hash=user.password_hash,
            failed_attempts=failed_attempts,
            lockout_until=lockout_until,
            password_reset_required=user.password_reset_required,
        )

    def clear_failed_attempts(self, user_id: str) -> None:
        user = self.users[user_id]
        self.users[user_id] = UserRecord(
            user_id=user.user_id,
            username=user.username,
            mobile=user.mobile,
            password_hash=user.password_hash,
            failed_attempts=0,
            lockout_until=None,
            password_reset_required=user.password_reset_required,
        )


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.created_for_user_ids: list[str] = []

    def create_session(
        self,
        *,
        user_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> SessionRecord:
        self.created_for_user_ids.append(user_id)
        return SessionRecord(
            session_id=f"session-{user_id}",
            user_id=user_id,
            token=f"token-{user_id}",
            expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=12),
        )


class StaticPasswordVerifier:
    def __init__(self, valid_password: str) -> None:
        self.valid_password = valid_password

    def verify(self, password_hash: str, plain_password: str) -> bool:
        return plain_password == self.valid_password and password_hash == "stored-hash"


@dataclass
class RecordingPasswordResetHook:
    called_with: list[str]

    def on_password_reset_required(self, user_id: str) -> None:
        self.called_with.append(user_id)


def test_login_supports_username_or_mobile_and_creates_session() -> None:
    user_repository = InMemoryUserRepository(
        [
            UserRecord(
                user_id="u-1",
                username="alice",
                mobile="+15551230000",
                password_hash="stored-hash",
                failed_attempts=2,
                lockout_until=None,
            )
        ]
    )
    session_repository = InMemorySessionRepository()
    service = AuthService(
        user_repository=user_repository,
        session_repository=session_repository,
        password_verifier=StaticPasswordVerifier(valid_password="correct-password"),
    )

    username_result = service.login(
        LoginRequest(identifier="alice", password="correct-password")
    )
    mobile_result = service.login(
        LoginRequest(identifier="+15551230000", password="correct-password")
    )

    assert username_result.success is True
    assert mobile_result.success is True
    assert session_repository.created_for_user_ids == ["u-1", "u-1"]
    assert user_repository.users["u-1"].failed_attempts == 0


def test_login_is_throttled_and_locks_user_after_max_attempts() -> None:
    user_repository = InMemoryUserRepository(
        [
            UserRecord(
                user_id="u-2",
                username="bob",
                mobile=None,
                password_hash="stored-hash",
                failed_attempts=2,
                lockout_until=None,
            )
        ]
    )
    service = AuthService(
        user_repository=user_repository,
        session_repository=InMemorySessionRepository(),
        password_verifier=StaticPasswordVerifier(valid_password="correct-password"),
        throttle_policy=ThrottlePolicy(max_attempts=3, lockout_seconds=60),
    )

    result = service.login(LoginRequest(identifier="bob", password="wrong-password"))

    assert result.success is False
    assert result.failure_code == AuthFailureCode.LOCKED_OUT
    assert result.lockout_until is not None
    assert user_repository.users["u-2"].failed_attempts == 3
    assert user_repository.users["u-2"].lockout_until is not None


def test_password_reset_hook_runs_when_login_requires_reset() -> None:
    user_repository = InMemoryUserRepository(
        [
            UserRecord(
                user_id="u-3",
                username="charlie",
                mobile="+15550003333",
                password_hash="stored-hash",
                failed_attempts=0,
                lockout_until=None,
                password_reset_required=True,
            )
        ]
    )
    hook = RecordingPasswordResetHook(called_with=[])
    service = AuthService(
        user_repository=user_repository,
        session_repository=InMemorySessionRepository(),
        password_verifier=StaticPasswordVerifier(valid_password="correct-password"),
        password_reset_hook=hook,
    )

    result = service.login(
        LoginRequest(identifier="charlie", password="correct-password")
    )

    assert result.success is True
    assert result.password_reset_required is True
    assert hook.called_with == ["u-3"]
