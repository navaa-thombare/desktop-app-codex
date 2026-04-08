from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AuthFailureCode(str, Enum):
    INVALID_CREDENTIALS = "invalid_credentials"
    LOCKED_OUT = "locked_out"


@dataclass(frozen=True)
class LoginRequest:
    identifier: str
    password: str
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    username: str
    mobile: str | None
    password_hash: str
    failed_attempts: int
    lockout_until: datetime | None
    password_reset_required: bool = False


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    user_id: str
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class LoginResult:
    success: bool
    failure_code: AuthFailureCode | None = None
    session: SessionRecord | None = None
    lockout_until: datetime | None = None
    password_reset_required: bool = False


@dataclass(frozen=True)
class ThrottlePolicy:
    max_attempts: int = 5
    lockout_seconds: int = 900
