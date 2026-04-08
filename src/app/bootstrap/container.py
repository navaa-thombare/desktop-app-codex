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
from app.platform.config.settings import AppSettings
from app.platform.db.session import build_engine, build_session_factory


@dataclass(frozen=True)
class Container:
    """Simple DI container composed at startup."""

    settings: AppSettings
    engine: object
    session_factory: sessionmaker
    auth_service: AuthService


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
    auth_service = AuthService(
        user_repository=user_repository,
        session_repository=InMemorySessionRepository(),
        password_verifier=Sha256PasswordVerifier(pepper=demo_pepper),
    )
    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        auth_service=auth_service,
    )
