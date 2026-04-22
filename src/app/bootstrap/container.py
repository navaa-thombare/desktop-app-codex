from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.admin.services import AdminUserManagementService
from app.auth.in_memory import (
    InMemorySessionRepository,
    Sha256PasswordVerifier,
)
from app.auth.sqlalchemy import SqlUserRepository
from app.auth.services import AuthService
from app.authorization.managed import (
    ManagedAuthorizationRoleRepository,
    ManagedAuthorizationUserRoleRepository,
)
from app.authorization.services import (
    AuthorizationGuard,
    AuthorizationService,
    EffectivePermissionService,
    ReportingService,
)
from app.operations.services import OperationsService
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
    admin_user_management_service: AdminUserManagementService
    operations_service: OperationsService


def build_container(settings: AppSettings) -> Container:
    engine = build_engine(settings.db_url, settings.db_echo)
    session_factory = build_session_factory(engine)

    demo_pepper = "desktop-app-demo-pepper"
    password_manager = Sha256PasswordVerifier(pepper=demo_pepper)
    audit_repository = InMemoryAuditEventRepository()
    audit_service = AuditService(repository=audit_repository)
    audit_review_service = AuditReviewService(repository=audit_repository)
    admin_user_management_service = AdminUserManagementService(
        engine=engine,
        session_factory=session_factory,
        password_hasher=password_manager.hash,
        bootstrap_password="ChangeMe123!",
    )
    operations_service = OperationsService(
        engine=engine,
        session_factory=session_factory,
    )
    user_repository = SqlUserRepository(session_factory=session_factory)

    auth_service = AuthService(
        user_repository=user_repository,
        session_repository=InMemorySessionRepository(),
        password_verifier=password_manager,
        audit_service=audit_service,
    )

    role_repository = ManagedAuthorizationRoleRepository()
    user_role_repository = ManagedAuthorizationUserRoleRepository(
        user_management_service=admin_user_management_service,
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
        admin_user_management_service=admin_user_management_service,
        operations_service=operations_service,
    )
