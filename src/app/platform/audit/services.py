from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timezone
from uuid import uuid4

from app.platform.audit.dtos import (
    AuditActor,
    AuditEvent,
    AuditEventType,
    AuditQuery,
    AuditReviewRow,
    utcnow,
)
from app.platform.audit.repositories import AuditEventRepository

logger = logging.getLogger(__name__)


@dataclass
class AuditService:
    repository: AuditEventRepository

    def publish(
        self,
        *,
        event_type: AuditEventType,
        correlation_id: str,
        actor: AuditActor,
        payload: dict[str, object],
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            occurred_at=utcnow(),
            correlation_id=correlation_id,
            actor=actor,
            payload=payload,
        )
        self.repository.append(event)
        logger.info(
            "audit_event_recorded",
            extra={
                "event_type": event.event_type.value,
                "correlation_id": correlation_id,
                "actor_id": actor.actor_id,
                "audit_payload": payload,
            },
        )
        return event


@dataclass
class AuditReviewService:
    repository: AuditEventRepository

    def query(self, query: AuditQuery) -> list[AuditReviewRow]:
        events = self.repository.query(query)
        rows: list[AuditReviewRow] = []
        for event in events:
            actor_id = event.actor.actor_id or "system"
            rows.append(
                AuditReviewRow(
                    occurred_at=event.occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    event_type=event.event_type.value,
                    actor_id=actor_id,
                    correlation_id=event.correlation_id,
                    summary=json.dumps(event.payload, sort_keys=True),
                )
            )
        return rows
