"""Authentication module contracts and services."""

from app.auth.dtos import AuthFailureCode, LoginRequest, LoginResult, SessionRecord, UserRecord
from app.auth.sqlalchemy import SqlUserRepository
from app.auth.services import (
    Argon2idPasswordVerifier,
    AuthService,
    PasswordRecoveryResult,
    PasswordResetHook,
    PasswordVerifier,
)

__all__ = [
    "Argon2idPasswordVerifier",
    "AuthFailureCode",
    "AuthService",
    "LoginRequest",
    "LoginResult",
    "PasswordRecoveryResult",
    "PasswordResetHook",
    "PasswordVerifier",
    "SessionRecord",
    "SqlUserRepository",
    "UserRecord",
]
