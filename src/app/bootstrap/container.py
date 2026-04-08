from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.platform.config.settings import AppSettings
from app.platform.db.session import build_engine, build_session_factory


@dataclass(frozen=True)
class Container:
    """Simple DI container composed at startup."""

    settings: AppSettings
    engine: object
    session_factory: sessionmaker


def build_container(settings: AppSettings) -> Container:
    engine = build_engine(settings.db_url, settings.db_echo)
    session_factory = build_session_factory(engine)
    return Container(settings=settings, engine=engine, session_factory=session_factory)
