from __future__ import annotations

from datetime import datetime, timezone

from app.auth.dtos import LoginRequest, UserRecord
from app.auth.services import AuthService
from app.platform.audit.dtos import AuditActor, AuditEventType, AuditQuery
from app.platform.audit.in_memory import InMemoryAuditEventRepository
from app.platform.audit.services import AuditReviewService, AuditService


class InMemoryUserRepository:
    def __init__(self, users: list[UserRecord]) -> None:
        self.users = {user.user_id: user for user in users}

    def get_by_username(self, username: str) -> UserRecord | None:
        return next((u for u in self.users.values() if u.username == username), None)

    def get_by_mobile(self, mobile: str) -> UserRecord | None:
        return next((u for u in self.users.values() if u.mobile == mobile), None)

    def register_failed_attempt(self, user_id: str, failed_attempts: int, lockout_until: datetime | None) -> None:
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
    def create_session(self, *, user_id: str, ip_address: str | None, user_agent: str | None):
        from app.auth.dtos import SessionRecord

        return SessionRecord(
            session_id=f"session-{user_id}",
            user_id=user_id,
            token="tkn",
            expires_at=datetime.now(timezone.utc),
        )


class StaticPasswordVerifier:
    def verify(self, password_hash: str, plain_password: str) -> bool:
        return password_hash == "stored-hash" and plain_password == "valid"


def test_login_events_published_with_correlation_id() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditService(repository=repository)
    auth_service = AuthService(
        user_repository=InMemoryUserRepository(
            [
                UserRecord(
                    user_id="u-1",
                    username="alice",
                    mobile="+1",
                    password_hash="stored-hash",
                    failed_attempts=0,
                    lockout_until=None,
                )
            ]
        ),
        session_repository=InMemorySessionRepository(),
        password_verifier=StaticPasswordVerifier(),
        audit_service=audit_service,
    )

    auth_service.login(
        LoginRequest(
            identifier="alice",
            password="valid",
            ip_address="127.0.0.1",
            correlation_id="corr-123",
        )
    )

    events = repository.query(AuditQuery(limit=10))
    assert len(events) == 1
    assert events[0].event_type == AuditEventType.LOGIN_SUCCEEDED
    assert events[0].correlation_id == "corr-123"


def test_audit_review_query_supports_event_type_and_actor_filters() -> None:
    repository = InMemoryAuditEventRepository()
    service = AuditService(repository=repository)
    review = AuditReviewService(repository=repository)

    service.publish(
        event_type=AuditEventType.ADMIN_CHANGE,
        correlation_id="corr-admin",
        actor=AuditActor(actor_id="u-admin"),
        payload={"action": "assign", "target": "role"},
    )
    service.publish(
        event_type=AuditEventType.PERMISSION_CHANGE,
        correlation_id="corr-perm",
        actor=AuditActor(actor_id="u-admin"),
        payload={"action": "unassign", "target": "permission"},
    )

    rows = review.query(AuditQuery(event_type=AuditEventType.PERMISSION_CHANGE, actor_id="u-admin"))

    assert len(rows) == 1
    assert rows[0].event_type == AuditEventType.PERMISSION_CHANGE.value
    assert rows[0].correlation_id == "corr-perm"
