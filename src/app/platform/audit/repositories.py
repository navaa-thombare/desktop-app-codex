from __future__ import annotations

from typing import Protocol

from app.platform.audit.dtos import AuditEvent, AuditQuery


class AuditEventRepository(Protocol):
    def append(self, event: AuditEvent) -> None:
        ...

    def query(self, query: AuditQuery) -> list[AuditEvent]:
        ...
