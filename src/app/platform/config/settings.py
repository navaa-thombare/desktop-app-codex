from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
