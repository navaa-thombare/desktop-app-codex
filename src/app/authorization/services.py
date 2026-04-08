from __future__ import annotations

from dataclasses import dataclass

from app.authorization.dtos import (
    AuthorizationContext,
    EffectivePermissions,
    PermissionEffect,
)
from app.authorization.repositories import RoleRepository, UserRoleRepository


class AuthorizationDeniedError(PermissionError):
    def __init__(self, permission: str) -> None:
        super().__init__(f"Missing required permission: {permission}")
        self.permission = permission


@dataclass
class AuthorizationService:
    role_repository: RoleRepository
    user_role_repository: UserRoleRepository

    def build_context(self, user_id: str) -> AuthorizationContext:
        role_ids = self.user_role_repository.list_role_ids_for_user(user_id)
        roles = tuple(
            role
            for role_id in role_ids
            if (role := self.role_repository.get_role(role_id)) is not None
        )
        return AuthorizationContext(user_id=user_id, roles=roles)


class EffectivePermissionService:
    def calculate(self, context: AuthorizationContext) -> EffectivePermissions:
        allowed: set[str] = set()
        denied: set[str] = set()

        for role in context.roles:
            for grant in role.grants:
                if grant.effect == PermissionEffect.DENY:
                    denied.add(grant.permission)
                else:
                    allowed.add(grant.permission)

        allowed.difference_update(denied)
        return EffectivePermissions(allowed=frozenset(allowed), denied=frozenset(denied))


@dataclass
class AuthorizationGuard:
    permission_service: EffectivePermissionService

    def can(self, *, permission: str, context: AuthorizationContext) -> bool:
        # Deny-by-default: any permission not explicitly allowed is denied.
        effective_permissions = self.permission_service.calculate(context)
        return effective_permissions.is_allowed(permission)

    def require(self, *, permission: str, context: AuthorizationContext) -> None:
        if not self.can(permission=permission, context=context):
            raise AuthorizationDeniedError(permission)


@dataclass
class ReportingService:
    authorization_service: AuthorizationService
    authorization_guard: AuthorizationGuard

    def run_operational_report(self, *, user_id: str) -> str:
        context = self.authorization_service.build_context(user_id)
        self.authorization_guard.require(permission="report:run", context=context)
        return "Operational report generated successfully."
