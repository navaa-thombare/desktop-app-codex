from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_engine(db_url: str, echo: bool):
    return create_engine(db_url, echo=echo, future=True)


def build_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
