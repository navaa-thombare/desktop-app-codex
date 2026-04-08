from __future__ import annotations

from datetime import timezone
from uuid import uuid4

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.auth.dtos import AuthFailureCode, LoginRequest
from app.auth.services import AuthService
from app.authorization.services import (
    AuthorizationDeniedError,
    AuthorizationGuard,
    AuthorizationService,
    ReportingService,
)
from app.desktop_shell.ui.admin_management import AccessControlWorkspace
from app.platform.audit import AuditReviewService, AuditService


class MainWindow(QMainWindow):
    def __init__(
        self,
        app_name: str,
        auth_service: AuthService,
        authorization_service: AuthorizationService,
        authorization_guard: AuthorizationGuard,
        reporting_service: ReportingService,
        audit_service: AuditService,
        audit_review_service: AuditReviewService,
    ) -> None:
        super().__init__()
        self._auth_service = auth_service
        self._authorization_service = authorization_service
        self._authorization_guard = authorization_guard
        self._reporting_service = reporting_service
        self._audit_service = audit_service
        self._audit_review_service = audit_review_service
        self._current_user_id: str | None = None
        self._is_loading = False

        self.setWindowTitle(f"{app_name} • Login")
        self.setMinimumWidth(520)

        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        heading = QLabel("Sign in")
        heading.setStyleSheet("font-size: 24px; font-weight: 600;")
        subheading = QLabel("Use your username or mobile number.")
        subheading.setStyleSheet("color: #555;")

        form = QFormLayout()
        form.setLabelAlignment(form.labelAlignment())

        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("username or +15551230000")
        self.identifier_input.returnPressed.connect(self._attempt_login)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.returnPressed.connect(self._attempt_login)

        form.addRow("Identifier", self.identifier_input)
        form.addRow("Password", self.password_input)

        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("color: #b00020;")

        actions = QHBoxLayout()
        self.login_button = QPushButton("Sign in")
        self.login_button.clicked.connect(self._attempt_login)

        self.reset_button = QPushButton("Forgot / Reset password")
        self.reset_button.setFlat(True)
        self.reset_button.clicked.connect(self._show_reset_placeholder)

        actions.addWidget(self.login_button)
        actions.addStretch(1)
        actions.addWidget(self.reset_button)

        self.nav_label = QLabel("Authorized Navigation")
        self.nav_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.nav_label.hide()

        nav_row = QHBoxLayout()
        self.nav_home_button = QPushButton("Home")
        self.nav_admin_button = QPushButton("Admin Console")
        self.nav_billing_button = QPushButton("Billing")

        nav_row.addWidget(self.nav_home_button)
        nav_row.addWidget(self.nav_admin_button)
        nav_row.addWidget(self.nav_billing_button)

        self.nav_home_button.clicked.connect(lambda: self._navigate("Home"))
        self.nav_admin_button.clicked.connect(lambda: self._navigate("Admin Console"))
        self.nav_billing_button.clicked.connect(lambda: self._navigate("Billing"))

        self.report_button = QPushButton("Run Operational Report")
        self.report_button.clicked.connect(self._run_operational_report)
        self.report_button.hide()

        layout.addWidget(heading)
        layout.addWidget(subheading)
        layout.addLayout(form)
        layout.addWidget(self.validation_label)
        layout.addLayout(actions)
        layout.addWidget(self.nav_label)
        layout.addLayout(nav_row)
        layout.addWidget(self.report_button)

        self.nav_home_button.hide()
        self.nav_admin_button.hide()
        self.nav_billing_button.hide()

        self.setCentralWidget(root)

    def _attempt_login(self) -> None:
        if self._is_loading:
            return

        identifier = self.identifier_input.text().strip()
        password = self.password_input.text()

        if not identifier or not password:
            self.validation_label.setText("Enter both identifier and password.")
            return

        self.validation_label.setText("")
        self._set_loading(True)

        QTimer.singleShot(450, lambda: self._authenticate(identifier=identifier, password=password))

    def _authenticate(self, *, identifier: str, password: str) -> None:
        result = self._auth_service.login(
            LoginRequest(
                identifier=identifier,
                password=password,
                user_agent="desktop-app/qt",
                correlation_id=str(uuid4()),
            )
        )

        self._set_loading(False)

        if result.success and result.session:
            self.password_input.clear()
            self._current_user_id = result.session.user_id
            self.validation_label.setStyleSheet("color: #1b5e20;")
            success_message = "Login successful. Your secure session is now active."
            if result.password_reset_required:
                success_message += " Password reset is required before continuing."
            self.validation_label.setText(success_message)

            expiry = result.session.expires_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            QMessageBox.information(
                self,
                "Welcome",
                f"Authenticated successfully. Session expires at {expiry}.",
            )
            self._render_authorized_navigation()
            self.validation_label.setStyleSheet("color: #b00020;")
            return

        self.password_input.clear()
        if result.failure_code == AuthFailureCode.LOCKED_OUT and result.lockout_until:
            unlock_at = result.lockout_until.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            self.validation_label.setText(
                f"Too many attempts. Account temporarily locked until {unlock_at}."
            )
            return

        self.validation_label.setText("Unable to sign in with those credentials.")

    def _render_authorized_navigation(self) -> None:
        if self._current_user_id is None:
            return

        self.nav_label.show()
        self.nav_home_button.show()
        self.nav_admin_button.show()
        self.nav_billing_button.show()
        self.report_button.show()

        context = self._authorization_service.build_context(self._current_user_id)
        nav_checks = {
            self.nav_home_button: "nav:home",
            self.nav_admin_button: "nav:admin",
            self.nav_billing_button: "nav:billing",
        }

        for button, permission in nav_checks.items():
            is_allowed = self._authorization_guard.can(permission=permission, context=context)
            button.setEnabled(is_allowed)
            button.setToolTip("" if is_allowed else f"Access denied by default for {permission}")

        report_allowed = self._authorization_guard.can(permission="report:run", context=context)
        self.report_button.setEnabled(report_allowed)
        self.report_button.setToolTip(
            "" if report_allowed else "Access denied by default for report:run"
        )

    def _run_operational_report(self) -> None:
        if self._current_user_id is None:
            return

        try:
            report_status = self._reporting_service.run_operational_report(
                user_id=self._current_user_id
            )
        except AuthorizationDeniedError as exc:
            QMessageBox.warning(self, "Authorization Denied", str(exc))
            return

        QMessageBox.information(self, "Report", report_status)

    def _navigate(self, destination: str) -> None:
        if destination == "Admin Console":
            AccessControlWorkspace(
                current_user_id=self._current_user_id,
                audit_service=self._audit_service,
                audit_review_service=self._audit_review_service,
                parent=self,
            ).exec()
            return

        QMessageBox.information(self, "Navigation", f"Navigated to {destination}.")

    def _set_loading(self, is_loading: bool) -> None:
        self._is_loading = is_loading
        self.identifier_input.setDisabled(is_loading)
        self.password_input.setDisabled(is_loading)
        self.login_button.setDisabled(is_loading)
        self.reset_button.setDisabled(is_loading)
        self.login_button.setText("Signing in..." if is_loading else "Sign in")

    def _show_reset_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "Reset Password",
            "Password reset flow is not wired yet. Please contact support for account recovery.",
        )
