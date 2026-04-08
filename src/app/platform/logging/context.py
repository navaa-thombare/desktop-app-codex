from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

_CORRELATION_ID: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _CORRELATION_ID.get()


def ensure_correlation_id(seed: str | None = None) -> str:
    existing = _CORRELATION_ID.get()
    if existing:
        return existing
    correlation_id = seed or str(uuid4())
    _CORRELATION_ID.set(correlation_id)
    return correlation_id


def set_correlation_id(correlation_id: str) -> None:
    _CORRELATION_ID.set(correlation_id)


@contextmanager
def correlation_context(correlation_id: str | None = None):
    token = _CORRELATION_ID.set(correlation_id or str(uuid4()))
    try:
        yield _CORRELATION_ID.get()
    finally:
        _CORRELATION_ID.reset(token)
