from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.bootstrap.container import Container, build_container
from app.desktop_shell.ui.main_window import MainWindow
from app.platform.config.settings import AppSettings, get_settings
from app.platform.liquibase.runner import maybe_run_liquibase
from app.platform.logging.setup import configure_logging

logger = logging.getLogger(__name__)


def start_application(settings: AppSettings | None = None) -> int:
    active_settings = settings or get_settings()

    configure_logging(active_settings.app_log_level, active_settings.app_log_json)
    logger.info("Starting %s in %s", active_settings.app_name, active_settings.app_env)

    # Safe checkpoint: perform DB migration before creating DB-dependent services/UI.
    maybe_run_liquibase(
        enabled=active_settings.liquibase_enabled,
        command=active_settings.liquibase_command,
        changelog_file=active_settings.liquibase_changelog_file,
        contexts=active_settings.liquibase_contexts,
        labels=active_settings.liquibase_labels,
    )

    container: Container = build_container(active_settings)
    logger.debug("Container initialized with DB URL %s", container.settings.db_url)

    qt_app = QApplication(sys.argv)
    qt_app.setFont(QFont("Nirmala UI", 10))
    window = MainWindow(
        container.settings.app_name,
        container.auth_service,
        container.authorization_service,
        container.authorization_guard,
        container.reporting_service,
        container.audit_service,
        container.audit_review_service,
        container.admin_user_management_service,
        container.operations_service,
        app_env=container.settings.app_env,
    )
    window.show()
    return qt_app.exec()
