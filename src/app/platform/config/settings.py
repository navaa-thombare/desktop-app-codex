from __future__ import annotations

import os
from functools import lru_cache

try:
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - used only in constrained environments
    BaseSettings = object
    Field = None
    SettingsConfigDict = None


if Field is not None and SettingsConfigDict is not None:

    class AppSettings(BaseSettings):
        """Environment-driven application settings."""

        model_config = SettingsConfigDict(
            env_file=".env", env_file_encoding="utf-8", extra="ignore"
        )

        app_name: str = Field(default="Desktop App", alias="APP_NAME")
        app_env: str = Field(default="development", alias="APP_ENV")
        app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
        app_log_json: bool = Field(default=False, alias="APP_LOG_JSON")

        db_url: str = Field(default="sqlite+pysqlite:///./desktop_app.db", alias="DB_URL")
        db_echo: bool = Field(default=False, alias="DB_ECHO")

        liquibase_enabled: bool = Field(default=False, alias="LIQUIBASE_ENABLED")
        liquibase_command: str = Field(default="liquibase", alias="LIQUIBASE_COMMAND")
        liquibase_changelog_file: str = Field(
            default="liquibase/changelog/db.changelog-master.xml",
            alias="LIQUIBASE_CHANGELOG_FILE",
        )
        liquibase_contexts: str = Field(default="common", alias="LIQUIBASE_CONTEXTS")
        liquibase_labels: str | None = Field(default=None, alias="LIQUIBASE_LABELS")

else:

    class AppSettings:
        """Fallback settings when pydantic is unavailable."""

        def __init__(self) -> None:
            self.app_name = os.getenv("APP_NAME", "Desktop App")
            self.app_env = os.getenv("APP_ENV", "development")
            self.app_log_level = os.getenv("APP_LOG_LEVEL", "INFO")
            self.app_log_json = _as_bool(os.getenv("APP_LOG_JSON"), default=False)
            self.db_url = os.getenv("DB_URL", "sqlite+pysqlite:///./desktop_app.db")
            self.db_echo = _as_bool(os.getenv("DB_ECHO"), default=False)
            self.liquibase_enabled = _as_bool(
                os.getenv("LIQUIBASE_ENABLED"), default=False
            )
            self.liquibase_command = os.getenv("LIQUIBASE_COMMAND", "liquibase")
            self.liquibase_changelog_file = os.getenv(
                "LIQUIBASE_CHANGELOG_FILE",
                "liquibase/changelog/db.changelog-master.xml",
            )
            self.liquibase_contexts = os.getenv("LIQUIBASE_CONTEXTS", "common")
            self.liquibase_labels = os.getenv("LIQUIBASE_LABELS")


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
