from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.auth.dtos import UserRecord
from app.auth.in_memory import (
    InMemorySessionRepository,
    InMemoryUserRepository,
    Sha256PasswordVerifier,
    hash_password,
)
from app.auth.services import AuthService
from app.authorization.dtos import PermissionEffect, PermissionGrant, RoleRecord
from app.authorization.in_memory import InMemoryRoleRepository, InMemoryUserRoleRepository
from app.authorization.services import (
    AuthorizationGuard,
    AuthorizationService,
    EffectivePermissionService,
    ReportingService,
)
from app.platform.audit.in_memory import InMemoryAuditEventRepository
from app.platform.audit.services import AuditReviewService, AuditService
from app.platform.config.settings import AppSettings
from app.platform.db.session import build_engine, build_session_factory


@dataclass(frozen=True)
class Container:
    """Simple DI container composed at startup."""

    settings: AppSettings
    engine: object
    session_factory: sessionmaker
    auth_service: AuthService
    authorization_service: AuthorizationService
    authorization_guard: AuthorizationGuard
    reporting_service: ReportingService
    audit_service: AuditService
    audit_review_service: AuditReviewService


def build_container(settings: AppSettings) -> Container:
    engine = build_engine(settings.db_url, settings.db_echo)
    session_factory = build_session_factory(engine)

    demo_pepper = "desktop-app-demo-pepper"
    user_repository = InMemoryUserRepository(
        users=[
            UserRecord(
                user_id="u-demo-1",
                username="admin",
                mobile="+15551230000",
                password_hash=hash_password("ChangeMe123!", pepper=demo_pepper),
                failed_attempts=0,
                lockout_until=None,
                password_reset_required=True,
            )
        ]
    )
    audit_repository = InMemoryAuditEventRepository()
    audit_service = AuditService(repository=audit_repository)
    audit_review_service = AuditReviewService(repository=audit_repository)

    auth_service = AuthService(
        user_repository=user_repository,
        session_repository=InMemorySessionRepository(),
        password_verifier=Sha256PasswordVerifier(pepper=demo_pepper),
        audit_service=audit_service,
    )

    role_repository = InMemoryRoleRepository(
        roles=[
            RoleRecord(
                role_id="role.admin",
                name="Administrator",
                grants=(
                    PermissionGrant(permission="nav:home", effect=PermissionEffect.ALLOW),
                    PermissionGrant(permission="nav:admin", effect=PermissionEffect.ALLOW),
                    PermissionGrant(permission="report:run", effect=PermissionEffect.ALLOW),
                ),
            ),
            RoleRecord(
                role_id="role.billing-restricted",
                name="Billing Restricted",
                grants=(
                    PermissionGrant(permission="nav:billing", effect=PermissionEffect.DENY),
                ),
            ),
        ]
    )
    user_role_repository = InMemoryUserRoleRepository(
        user_roles={
            "u-demo-1": ("role.admin", "role.billing-restricted"),
        }
    )

    authorization_service = AuthorizationService(
        role_repository=role_repository,
        user_role_repository=user_role_repository,
    )
    authorization_guard = AuthorizationGuard(permission_service=EffectivePermissionService())
    reporting_service = ReportingService(
        authorization_service=authorization_service,
        authorization_guard=authorization_guard,
    )

    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        auth_service=auth_service,
        authorization_service=authorization_service,
        authorization_guard=authorization_guard,
        reporting_service=reporting_service,
        audit_service=audit_service,
        audit_review_service=audit_review_service,
    )
