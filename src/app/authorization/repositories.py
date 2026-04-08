from __future__ import annotations

from typing import Protocol

from app.authorization.dtos import RoleRecord


class RoleRepository(Protocol):
    def get_role(self, role_id: str) -> RoleRecord | None:
        ...


class UserRoleRepository(Protocol):
    def list_role_ids_for_user(self, user_id: str) -> tuple[str, ...]:
        ...
