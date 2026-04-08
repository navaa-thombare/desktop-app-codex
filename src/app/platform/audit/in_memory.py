from __future__ import annotations

from app.platform.audit.dtos import AuditEvent, AuditQuery


class InMemoryAuditEventRepository:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def query(self, query: AuditQuery) -> list[AuditEvent]:
        filtered = list(self._events)

        if query.event_type is not None:
            filtered = [e for e in filtered if e.event_type == query.event_type]
        if query.actor_id:
            filtered = [e for e in filtered if e.actor.actor_id == query.actor_id]
        if query.correlation_id:
            filtered = [e for e in filtered if e.correlation_id == query.correlation_id]
        if query.since:
            filtered = [e for e in filtered if e.occurred_at >= query.since]
        if query.until:
            filtered = [e for e in filtered if e.occurred_at <= query.until]

        filtered.sort(key=lambda e: e.occurred_at, reverse=True)
        return filtered[: query.limit]
