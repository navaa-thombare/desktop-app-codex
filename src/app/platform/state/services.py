from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class AppStateModel(Base):
    __tablename__ = "app_runtime_state"

    state_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class AppStateService:
    engine: object
    session_factory: sessionmaker[Session]

    def __post_init__(self) -> None:
        Base.metadata.create_all(bind=self.engine)

    def save_shell_state(self, payload: dict[str, object]) -> None:
        with self.session_factory() as session:
            row = session.get(AppStateModel, "shell")
            encoded_payload = json.dumps(payload, sort_keys=True)
            now = datetime.now(tz=timezone.utc)
            if row is None:
                row = AppStateModel(
                    state_key="shell",
                    payload_json=encoded_payload,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.payload_json = encoded_payload
                row.updated_at = now
            session.commit()

    def load_shell_state(self) -> dict[str, object]:
        with self.session_factory() as session:
            row = session.get(AppStateModel, "shell")
            if row is None:
                return {}
            return json.loads(row.payload_json)
