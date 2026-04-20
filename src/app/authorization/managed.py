from __future__ import annotations

from dataclasses import dataclass

from app.admin.services import AdminUserManagementService
from app.authorization.dtos import PermissionEffect, PermissionGrant, RoleRecord

AUTHENTICATED_ROLE_ID = "managed.authenticated"
PERMISSION_ROLE_PREFIX = "managed.permission:"


@dataclass(frozen=True)
class ManagedAuthorizationRoleRepository:
    def get_role(self, role_id: str) -> RoleRecord | None:
        if role_id == AUTHENTICATED_ROLE_ID:
            return RoleRecord(
                role_id=AUTHENTICATED_ROLE_ID,
                name="Authenticated User",
                grants=(
                    PermissionGrant(permission="nav:home", effect=PermissionEffect.ALLOW),
                ),
            )

        if not role_id.startswith(PERMISSION_ROLE_PREFIX):
            return None

        permission = role_id.removeprefix(PERMISSION_ROLE_PREFIX)
        if not permission:
            return None

        return RoleRecord(
            role_id=role_id,
            name=f"Allow {permission}",
            grants=(
                PermissionGrant(permission=permission, effect=PermissionEffect.ALLOW),
            ),
        )


@dataclass(frozen=True)
class ManagedAuthorizationUserRoleRepository:
    user_management_service: AdminUserManagementService

    def list_role_ids_for_user(self, user_id: str) -> tuple[str, ...]:
        profile = self.user_management_service.get_user_profile(user_id)
        if profile is None:
            return ()

        role_ids = [AUTHENTICATED_ROLE_ID]
        role_ids.extend(
            f"{PERMISSION_ROLE_PREFIX}{permission_name}"
            for permission_name in profile.permissions
        )
        return tuple(dict.fromkeys(role_ids))
