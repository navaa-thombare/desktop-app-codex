from __future__ import annotations

from app.authorization.dtos import RoleRecord


class InMemoryRoleRepository:
    def __init__(self, roles: list[RoleRecord]) -> None:
        self._roles = {role.role_id: role for role in roles}

    def get_role(self, role_id: str) -> RoleRecord | None:
        return self._roles.get(role_id)


class InMemoryUserRoleRepository:
    def __init__(self, user_roles: dict[str, tuple[str, ...]]) -> None:
        self._user_roles = user_roles

    def list_role_ids_for_user(self, user_id: str) -> tuple[str, ...]:
        return self._user_roles.get(user_id, ())
