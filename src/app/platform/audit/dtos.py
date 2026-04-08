from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AuditEventType(str, Enum):
    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"
    ADMIN_CHANGE = "admin_change"
    PERMISSION_CHANGE = "permission_change"


@dataclass(frozen=True)
class AuditActor:
    actor_id: str | None
    actor_type: str = "user"


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: AuditEventType
    occurred_at: datetime
    correlation_id: str
    actor: AuditActor
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditQuery:
    event_type: AuditEventType | None = None
    actor_id: str | None = None
    correlation_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100


@dataclass(frozen=True)
class AuditReviewRow:
    occurred_at: str
    event_type: str
    actor_id: str
    correlation_id: str
    summary: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
