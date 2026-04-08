from __future__ import annotations

import pytest

from app.authorization.dtos import PermissionEffect, PermissionGrant, RoleRecord
from app.authorization.in_memory import InMemoryRoleRepository, InMemoryUserRoleRepository
from app.authorization.services import (
    AuthorizationDeniedError,
    AuthorizationGuard,
    AuthorizationService,
    EffectivePermissionService,
    ReportingService,
)


def test_effective_permission_calculation_respects_explicit_deny() -> None:
    context = AuthorizationService(
        role_repository=InMemoryRoleRepository(
            roles=[
                RoleRecord(
                    role_id="role.ops",
                    name="Operations",
                    grants=(
                        PermissionGrant(permission="report:run", effect=PermissionEffect.ALLOW),
                    ),
                ),
                RoleRecord(
                    role_id="role.audit-lock",
                    name="Audit Lock",
                    grants=(
                        PermissionGrant(permission="report:run", effect=PermissionEffect.DENY),
                    ),
                ),
            ]
        ),
        user_role_repository=InMemoryUserRoleRepository(
            user_roles={"u-1": ("role.ops", "role.audit-lock")}
        ),
    ).build_context("u-1")

    effective = EffectivePermissionService().calculate(context)

    assert effective.is_allowed("report:run") is False
    assert "report:run" in effective.denied


def test_guard_is_deny_by_default_when_permission_not_granted() -> None:
    service = AuthorizationService(
        role_repository=InMemoryRoleRepository(
            roles=[
                RoleRecord(
                    role_id="role.viewer",
                    name="Viewer",
                    grants=(
                        PermissionGrant(permission="nav:home", effect=PermissionEffect.ALLOW),
                    ),
                )
            ]
        ),
        user_role_repository=InMemoryUserRoleRepository(user_roles={"u-2": ("role.viewer",)}),
    )
    context = service.build_context("u-2")
    guard = AuthorizationGuard(permission_service=EffectivePermissionService())

    assert guard.can(permission="nav:home", context=context) is True
    assert guard.can(permission="nav:admin", context=context) is False


def test_reporting_service_blocks_execution_without_permission() -> None:
    authorization_service = AuthorizationService(
        role_repository=InMemoryRoleRepository(
            roles=[
                RoleRecord(
                    role_id="role.viewer",
                    name="Viewer",
                    grants=(
                        PermissionGrant(permission="nav:home", effect=PermissionEffect.ALLOW),
                    ),
                )
            ]
        ),
        user_role_repository=InMemoryUserRoleRepository(user_roles={"u-3": ("role.viewer",)}),
    )
    guard = AuthorizationGuard(permission_service=EffectivePermissionService())
    reporting_service = ReportingService(
        authorization_service=authorization_service,
        authorization_guard=guard,
    )

    with pytest.raises(AuthorizationDeniedError):
        reporting_service.run_operational_report(user_id="u-3")
