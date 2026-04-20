from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.admin.services import AdminUserManagementService
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


@dataclass(slots=True)
class SessionState:
    user_id: str
    identifier: str
    expires_at: datetime
    password_reset_required: bool


@dataclass(slots=True)
class PendingPasswordReset:
    user_id: str
    identifier: str
    expires_at: datetime | None = None
    activate_workspace_on_success: bool = False


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
        admin_user_management_service: AdminUserManagementService,
        app_env: str = "development",
    ) -> None:
        super().__init__()
        self._app_name = app_name
        self._app_env = app_env
        self._auth_service = auth_service
        self._authorization_service = authorization_service
        self._authorization_guard = authorization_guard
        self._reporting_service = reporting_service
        self._audit_service = audit_service
        self._audit_review_service = audit_review_service
        self._admin_user_management_service = admin_user_management_service
        self._current_user_id: str | None = None
        self._session_state: SessionState | None = None
        self._pending_password_reset: PendingPasswordReset | None = None
        self._is_loading = False
        self._active_route = "home"

        self.setWindowTitle(f"{app_name} | Secure Access")
        self.resize(1180, 780)
        self.setMinimumSize(1024, 680)

        self._pages = QStackedWidget(self)
        self.login_page = self._build_login_page()
        self.forgot_password_page = self._build_forgot_password_page()
        self.password_reset_page = self._build_password_reset_page()
        self.workspace_page = self._build_workspace_page()
        self._pages.addWidget(self.login_page)
        self._pages.addWidget(self.forgot_password_page)
        self._pages.addWidget(self.password_reset_page)
        self._pages.addWidget(self.workspace_page)
        self.setCentralWidget(self._pages)

        self._apply_styles()
        self._reset_workspace_state()

    def _build_login_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("LoginPage")

        layout = QHBoxLayout(page)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(24)

        splash_panel = QFrame()
        splash_panel.setObjectName("SplashPanel")
        splash_layout = QVBoxLayout(splash_panel)
        splash_layout.setContentsMargins(36, 36, 36, 36)
        splash_layout.setSpacing(18)

        hero_eyebrow = QLabel("TRUSTED OPERATIONS ACCESS")
        hero_eyebrow.setObjectName("HeroEyebrow")

        hero_title = QLabel(self._app_name)
        hero_title.setObjectName("HeroTitle")
        hero_title.setWordWrap(True)

        hero_subtitle = QLabel(
            "A secure planning workspace for identity-aware operations, "
            "audit review, and permissioned admin workflows."
        )
        hero_subtitle.setObjectName("HeroSubtitle")
        hero_subtitle.setWordWrap(True)

        feature_grid = QGridLayout()
        feature_grid.setHorizontalSpacing(14)
        feature_grid.setVerticalSpacing(14)
        feature_grid.addWidget(
            self._build_feature_card(
                "Policy-first access",
                "Navigation and reporting actions stay locked behind explicit permissions.",
            ),
            0,
            0,
        )
        feature_grid.addWidget(
            self._build_feature_card(
                "Traceable sign-ins",
                "Each authentication outcome carries a correlation trail for audit review.",
            ),
            0,
            1,
        )
        feature_grid.addWidget(
            self._build_feature_card(
                "Single-window routing",
                "Home, billing, and admin views render inside the same shell for a web-like flow.",
            ),
            1,
            0,
            1,
            2,
        )

        hero_footer = QLabel("Use the secure access panel to enter the workspace.")
        hero_footer.setObjectName("HeroFooter")
        hero_footer.setWordWrap(True)

        splash_layout.addWidget(hero_eyebrow)
        splash_layout.addWidget(hero_title)
        splash_layout.addWidget(hero_subtitle)
        splash_layout.addStretch(1)
        splash_layout.addLayout(feature_grid)
        splash_layout.addWidget(hero_footer)

        card_column = QVBoxLayout()
        card_column.setContentsMargins(0, 0, 0, 0)
        card_column.addStretch(1)

        login_card = QFrame()
        login_card.setObjectName("LoginCard")
        login_card.setMinimumWidth(380)
        login_card.setMaximumWidth(430)

        login_layout = QVBoxLayout(login_card)
        login_layout.setContentsMargins(28, 28, 28, 28)
        login_layout.setSpacing(14)

        card_eyebrow = QLabel("Welcome back")
        card_eyebrow.setObjectName("CardEyebrow")

        heading = QLabel("Sign in")
        heading.setObjectName("CardTitle")

        subheading = QLabel(
            "Enter your username or mobile number to continue into the application."
        )
        subheading.setObjectName("CardSubtitle")
        subheading.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("username or +15551230000")
        self.identifier_input.returnPressed.connect(self._attempt_login)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.returnPressed.connect(self._attempt_login)

        identifier_label = QLabel("Identifier")
        identifier_label.setObjectName("FormLabel")
        password_label = QLabel("Password")
        password_label.setObjectName("FormLabel")

        form.addRow(identifier_label, self.identifier_input)
        form.addRow(password_label, self.password_input)

        self.validation_label = QLabel("")
        self.validation_label.setObjectName("StatusMessage")
        self.validation_label.setWordWrap(True)
        self.validation_label.hide()

        self.login_button = QPushButton("Sign in")
        self.login_button.clicked.connect(self._attempt_login)
        self.login_button.setMinimumHeight(46)

        self.reset_button = QPushButton("Forgot / Reset password")
        self.reset_button.setObjectName("LinkButton")
        self.reset_button.clicked.connect(self._open_forgot_password_page)

        helper = QLabel(
            "Session activity is captured for operational audit and security review."
        )
        helper.setObjectName("CardHelper")
        helper.setWordWrap(True)

        login_layout.addWidget(card_eyebrow)
        login_layout.addWidget(heading)
        login_layout.addWidget(subheading)
        login_layout.addSpacing(6)
        login_layout.addLayout(form)
        login_layout.addWidget(self.validation_label)
        login_layout.addWidget(self.login_button)
        login_layout.addWidget(self.reset_button, alignment=Qt.AlignmentFlag.AlignLeft)
        login_layout.addWidget(helper)

        card_column.addWidget(login_card)
        card_column.addStretch(1)

        layout.addWidget(splash_panel, 7)
        layout.addLayout(card_column, 5)
        return page

    def _build_forgot_password_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("RecoveryPage")

        layout = QHBoxLayout(page)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(24)

        copy_panel = QFrame()
        copy_panel.setObjectName("SplashPanel")
        copy_layout = QVBoxLayout(copy_panel)
        copy_layout.setContentsMargins(36, 36, 36, 36)
        copy_layout.setSpacing(18)

        copy_eyebrow = QLabel("SELF-SERVICE PASSWORD RECOVERY")
        copy_eyebrow.setObjectName("HeroEyebrow")

        copy_title = QLabel("Recover account access")
        copy_title.setObjectName("HeroTitle")
        copy_title.setWordWrap(True)

        copy_text = QLabel(
            "Confirm the sign-in identifier and one registered contact value. "
            "Once verified, you can choose a new password immediately."
        )
        copy_text.setObjectName("HeroSubtitle")
        copy_text.setWordWrap(True)

        recovery_tip = QLabel(
            "Use the same mobile number or email stored in the user profile. "
            "The reset finishes inside this window and returns you to sign in."
        )
        recovery_tip.setObjectName("HeroFooter")
        recovery_tip.setWordWrap(True)

        copy_layout.addWidget(copy_eyebrow)
        copy_layout.addWidget(copy_title)
        copy_layout.addWidget(copy_text)
        copy_layout.addStretch(1)
        copy_layout.addWidget(recovery_tip)

        card_column = QVBoxLayout()
        card_column.setContentsMargins(0, 0, 0, 0)
        card_column.addStretch(1)

        recovery_card = QFrame()
        recovery_card.setObjectName("LoginCard")
        recovery_card.setMinimumWidth(400)
        recovery_card.setMaximumWidth(460)

        recovery_layout = QVBoxLayout(recovery_card)
        recovery_layout.setContentsMargins(28, 28, 28, 28)
        recovery_layout.setSpacing(14)

        card_eyebrow = QLabel("Password recovery")
        card_eyebrow.setObjectName("CardEyebrow")

        heading = QLabel("Verify identity")
        heading.setObjectName("CardTitle")

        subtitle = QLabel(
            "Enter your username or mobile number, then provide one registered contact detail."
        )
        subtitle.setObjectName("CardSubtitle")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.recovery_identifier_input = QLineEdit()
        self.recovery_identifier_input.setPlaceholderText("username or +15551230000")
        self.recovery_identifier_input.returnPressed.connect(self._verify_password_recovery)

        self.recovery_contact_input = QLineEdit()
        self.recovery_contact_input.setPlaceholderText("registered mobile number or email")
        self.recovery_contact_input.returnPressed.connect(self._verify_password_recovery)

        identifier_label = QLabel("Identifier")
        identifier_label.setObjectName("FormLabel")
        contact_label = QLabel("Registered contact")
        contact_label.setObjectName("FormLabel")
        form.addRow(identifier_label, self.recovery_identifier_input)
        form.addRow(contact_label, self.recovery_contact_input)

        self.recovery_status_label = QLabel("")
        self.recovery_status_label.setObjectName("StatusMessage")
        self.recovery_status_label.setWordWrap(True)
        self.recovery_status_label.hide()

        recovery_actions = QHBoxLayout()
        self.recovery_submit_button = QPushButton("Verify Identity")
        self.recovery_submit_button.clicked.connect(self._verify_password_recovery)
        self.recovery_back_button = QPushButton("Back to Sign in")
        self.recovery_back_button.setObjectName("SecondaryButton")
        self.recovery_back_button.clicked.connect(self._return_to_login_from_recovery)
        recovery_actions.addWidget(self.recovery_submit_button)
        recovery_actions.addWidget(self.recovery_back_button)

        recovery_layout.addWidget(card_eyebrow)
        recovery_layout.addWidget(heading)
        recovery_layout.addWidget(subtitle)
        recovery_layout.addSpacing(6)
        recovery_layout.addLayout(form)
        recovery_layout.addWidget(self.recovery_status_label)
        recovery_layout.addLayout(recovery_actions)

        card_column.addWidget(recovery_card)
        card_column.addStretch(1)

        layout.addWidget(copy_panel, 7)
        layout.addLayout(card_column, 5)
        return page

    def _build_password_reset_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("WorkspacePage")

        layout = QHBoxLayout(page)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(24)

        copy_panel = QFrame()
        copy_panel.setObjectName("SplashPanel")
        copy_layout = QVBoxLayout(copy_panel)
        copy_layout.setContentsMargins(36, 36, 36, 36)
        copy_layout.setSpacing(18)

        copy_eyebrow = QLabel("FIRST LOGIN SECURITY CHECKPOINT")
        copy_eyebrow.setObjectName("HeroEyebrow")

        copy_title = QLabel("Set a new password")
        copy_title.setObjectName("HeroTitle")
        copy_title.setWordWrap(True)

        copy_text = QLabel(
            "Temporary passwords are only valid for first access. Choose a new password before the session can enter the main workspace."
        )
        copy_text.setObjectName("HeroSubtitle")
        copy_text.setWordWrap(True)

        copy_layout.addWidget(copy_eyebrow)
        copy_layout.addWidget(copy_title)
        copy_layout.addWidget(copy_text)
        copy_layout.addStretch(1)

        card_column = QVBoxLayout()
        card_column.setContentsMargins(0, 0, 0, 0)
        card_column.addStretch(1)

        reset_card = QFrame()
        reset_card.setObjectName("LoginCard")
        reset_card.setMinimumWidth(420)
        reset_card.setMaximumWidth(460)

        reset_layout = QVBoxLayout(reset_card)
        reset_layout.setContentsMargins(28, 28, 28, 28)
        reset_layout.setSpacing(14)

        card_eyebrow = QLabel("Password reset required")
        card_eyebrow.setObjectName("CardEyebrow")

        heading = QLabel("Update password")
        heading.setObjectName("CardTitle")

        self.password_reset_identity_label = QLabel("Authenticate first to begin the password reset flow.")
        self.password_reset_identity_label.setObjectName("CardSubtitle")
        self.password_reset_identity_label.setWordWrap(True)

        helper = QLabel(
            "Use at least 12 characters with uppercase, lowercase, number, and special character."
        )
        helper.setObjectName("CardHelper")
        helper.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input.setPlaceholderText("Enter a new password")
        self.new_password_input.returnPressed.connect(self._submit_password_reset)

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setPlaceholderText("Confirm the new password")
        self.confirm_password_input.returnPressed.connect(self._submit_password_reset)

        new_password_label = QLabel("New password")
        new_password_label.setObjectName("FormLabel")
        confirm_password_label = QLabel("Confirm password")
        confirm_password_label.setObjectName("FormLabel")
        form.addRow(new_password_label, self.new_password_input)
        form.addRow(confirm_password_label, self.confirm_password_input)

        self.password_reset_status_label = QLabel("")
        self.password_reset_status_label.setObjectName("StatusMessage")
        self.password_reset_status_label.setWordWrap(True)
        self.password_reset_status_label.hide()

        reset_actions = QHBoxLayout()
        self.password_reset_submit_button = QPushButton("Update Password")
        self.password_reset_submit_button.clicked.connect(self._submit_password_reset)
        self.password_reset_cancel_button = QPushButton("Sign out")
        self.password_reset_cancel_button.setObjectName("SecondaryButton")
        self.password_reset_cancel_button.clicked.connect(self._cancel_password_reset)
        reset_actions.addWidget(self.password_reset_submit_button)
        reset_actions.addWidget(self.password_reset_cancel_button)

        reset_layout.addWidget(card_eyebrow)
        reset_layout.addWidget(heading)
        reset_layout.addWidget(self.password_reset_identity_label)
        reset_layout.addWidget(helper)
        reset_layout.addSpacing(6)
        reset_layout.addLayout(form)
        reset_layout.addWidget(self.password_reset_status_label)
        reset_layout.addLayout(reset_actions)

        card_column.addWidget(reset_card)
        card_column.addStretch(1)

        layout.addWidget(copy_panel, 7)
        layout.addLayout(card_column, 5)
        return page

    def _build_feature_card(self, title: str, detail: str) -> QFrame:
        card = QFrame()
        card.setObjectName("FeatureCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("FeatureTitle")

        detail_label = QLabel(detail)
        detail_label.setObjectName("FeatureDetail")
        detail_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(detail_label)
        return card

    def _build_workspace_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("WorkspacePage")

        root = QVBoxLayout(page)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        banner = QFrame()
        banner.setObjectName("WorkspaceBanner")

        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(28, 28, 28, 28)
        banner_layout.setSpacing(18)

        banner_copy = QVBoxLayout()
        banner_copy.setSpacing(8)

        workspace_eyebrow = QLabel("SESSION ACTIVE")
        workspace_eyebrow.setObjectName("WorkspaceEyebrow")

        self.workspace_heading = QLabel("Secure workspace")
        self.workspace_heading.setObjectName("WorkspaceTitle")

        self.workspace_summary_label = QLabel(
            "Sign in to unlock navigation and protected actions."
        )
        self.workspace_summary_label.setObjectName("WorkspaceSubtitle")
        self.workspace_summary_label.setWordWrap(True)

        banner_copy.addWidget(workspace_eyebrow)
        banner_copy.addWidget(self.workspace_heading)
        banner_copy.addWidget(self.workspace_summary_label)

        self.session_badge_label = QLabel("No active session")
        self.session_badge_label.setObjectName("SessionBadge")
        self.session_badge_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        banner_actions = QVBoxLayout()
        banner_actions.setSpacing(10)
        banner_actions.addWidget(
            self.session_badge_label,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        banner_actions.addStretch(1)

        self.reload_admin_ui_button = QPushButton("Reload Admin UI")
        self.reload_admin_ui_button.setObjectName("SecondaryButton")
        self.reload_admin_ui_button.setMinimumHeight(40)
        self.reload_admin_ui_button.setToolTip(
            "Development only: reload the admin workspace from source without restarting the app."
        )
        self.reload_admin_ui_button.clicked.connect(self._reload_admin_ui)
        self.reload_admin_ui_button.setVisible(self._app_env.lower() == "development")
        if self.reload_admin_ui_button.isVisible():
            banner_actions.addWidget(
                self.reload_admin_ui_button,
                alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            )

        banner_layout.addLayout(banner_copy, stretch=1)
        banner_layout.addLayout(banner_actions)

        shell = QHBoxLayout()
        shell.setSpacing(18)

        sidebar = QFrame()
        sidebar.setObjectName("WorkspaceSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 20, 20, 20)
        sidebar_layout.setSpacing(12)

        sidebar_heading = QLabel("Navigate")
        sidebar_heading.setObjectName("SidebarHeading")
        sidebar_layout.addWidget(sidebar_heading)

        self.nav_home_button = QPushButton("Home")
        self.nav_admin_button = QPushButton("Admin Console")
        self.nav_billing_button = QPushButton("Billing")
        self.logout_button = QPushButton("Sign out")
        self.logout_button.setObjectName("SecondaryButton")
        self.logout_button.clicked.connect(self._logout)

        self._nav_buttons = {
            "home": self.nav_home_button,
            "admin": self.nav_admin_button,
            "billing": self.nav_billing_button,
        }
        for route_key, button in self._nav_buttons.items():
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setMinimumHeight(46)
            button.clicked.connect(lambda _checked=False, key=route_key: self._navigate(key))
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch(1)
        sidebar_layout.addWidget(self.logout_button)

        content = QFrame()
        content.setObjectName("WorkspaceContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 26, 26, 26)
        content_layout.setSpacing(14)

        self.page_eyebrow = QLabel("CURRENT SECTION")
        self.page_eyebrow.setObjectName("PageEyebrow")

        self.page_title_label = QLabel("Home")
        self.page_title_label.setObjectName("PageTitle")

        self.page_subtitle_label = QLabel("Use the navigation rail to move through the app.")
        self.page_subtitle_label.setObjectName("PageSubtitle")
        self.page_subtitle_label.setWordWrap(True)

        self.workspace_notice = QLabel("")
        self.workspace_notice.setObjectName("StatusMessage")
        self.workspace_notice.setWordWrap(True)
        self.workspace_notice.hide()

        self.route_stack = QStackedWidget()
        self.home_page = self._build_home_page()
        self.admin_page = AccessControlWorkspace(
            current_user_id=self._current_user_id,
            audit_service=self._audit_service,
            audit_review_service=self._audit_review_service,
            user_management_service=self._admin_user_management_service,
            parent=self,
        )
        self.billing_page = self._build_billing_page()

        self.route_stack.addWidget(self.home_page)
        self.route_stack.addWidget(self.admin_page)
        self.route_stack.addWidget(self.billing_page)

        self._route_config = {
            "home": {
                "title": "Home",
                "subtitle": "Review the active session and run permissioned operational tasks.",
                "widget": self.home_page,
            },
            "admin": {
                "title": "Admin Console",
                "subtitle": "Manage users, roles, permissions, and audit review in the same workspace.",
                "widget": self.admin_page,
            },
            "billing": {
                "title": "Billing",
                "subtitle": "Billing screens render inside the shell and inherit the current session context.",
                "widget": self.billing_page,
            },
        }

        content_layout.addWidget(self.page_eyebrow)
        content_layout.addWidget(self.page_title_label)
        content_layout.addWidget(self.page_subtitle_label)
        content_layout.addWidget(self.workspace_notice)
        content_layout.addWidget(self.route_stack, stretch=1)

        shell.addWidget(sidebar, 2)
        shell.addWidget(content, 7)

        root.addWidget(banner)
        root.addLayout(shell, stretch=1)
        return page

    def _build_home_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        report_card = QFrame()
        report_card.setObjectName("InnerCard")
        report_layout = QVBoxLayout(report_card)
        report_layout.setContentsMargins(20, 20, 20, 20)
        report_layout.setSpacing(10)

        report_title = QLabel("Operational Reporting")
        report_title.setObjectName("SectionTitle")
        report_copy = QLabel(
            "Run secure reporting actions from the home route without leaving the current window."
        )
        report_copy.setObjectName("SectionCopy")
        report_copy.setWordWrap(True)

        self.report_button = QPushButton("Run Operational Report")
        self.report_button.setObjectName("ActionButton")
        self.report_button.setMinimumHeight(46)
        self.report_button.clicked.connect(self._run_operational_report)

        report_layout.addWidget(report_title)
        report_layout.addWidget(report_copy)
        report_layout.addWidget(self.report_button, alignment=Qt.AlignmentFlag.AlignLeft)

        session_card = QFrame()
        session_card.setObjectName("InnerCard")
        session_layout = QVBoxLayout(session_card)
        session_layout.setContentsMargins(20, 20, 20, 20)
        session_layout.setSpacing(10)

        session_title = QLabel("Session Context")
        session_title.setObjectName("SectionTitle")
        self.home_session_label = QLabel(
            "Sign in to populate session metadata and route-aware workspace details."
        )
        self.home_session_label.setObjectName("SectionCopy")
        self.home_session_label.setWordWrap(True)

        session_layout.addWidget(session_title)
        session_layout.addWidget(self.home_session_label)

        layout.addWidget(report_card)
        layout.addWidget(session_card)
        layout.addStretch(1)
        return page

    def _build_billing_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        billing_card = QFrame()
        billing_card.setObjectName("InnerCard")
        billing_layout = QVBoxLayout(billing_card)
        billing_layout.setContentsMargins(20, 20, 20, 20)
        billing_layout.setSpacing(10)

        billing_title = QLabel("Billing Workspace")
        billing_title.setObjectName("SectionTitle")
        billing_copy = QLabel(
            "This route is rendered inside the shared application shell so future billing flows can reuse the current session state and route header."
        )
        billing_copy.setObjectName("SectionCopy")
        billing_copy.setWordWrap(True)

        billing_note = QLabel(
            "Use this page as the in-app destination for invoices, collections, or reconciliation tools."
        )
        billing_note.setObjectName("SectionCopy")
        billing_note.setWordWrap(True)

        billing_layout.addWidget(billing_title)
        billing_layout.addWidget(billing_copy)
        billing_layout.addWidget(billing_note)

        layout.addWidget(billing_card)
        layout.addStretch(1)
        return page

    def _attempt_login(self) -> None:
        if self._is_loading:
            return

        identifier = self.identifier_input.text().strip()
        password = self.password_input.text()

        if not identifier or not password:
            self._set_status_label(
                self.validation_label,
                "Enter both identifier and password.",
                tone="error",
            )
            return

        self._set_status_label(self.validation_label, "", tone="error")
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
            self.admin_page.set_current_user_id(self._current_user_id)
            if result.password_reset_required:
                self._begin_password_reset(
                    user_id=self._current_user_id,
                    identifier=identifier,
                    expires_at=result.session.expires_at,
                    activate_workspace_on_success=True,
                )
                return
            self._activate_workspace(
                identifier=identifier,
                expires_at=result.session.expires_at,
                password_reset_required=result.password_reset_required,
            )
            self._render_authorized_navigation()
            self._navigate(self._default_route_key(), clear_notice=False)
            return

        self.password_input.clear()
        if result.failure_code == AuthFailureCode.LOCKED_OUT and result.lockout_until:
            unlock_at = result.lockout_until.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            self._set_status_label(
                self.validation_label,
                f"Too many attempts. Account temporarily locked until {unlock_at}.",
                tone="warning",
            )
            return

        self._set_status_label(
            self.validation_label,
            "Unable to sign in with those credentials.",
            tone="error",
        )

    def _begin_password_reset(
        self,
        *,
        user_id: str | None,
        identifier: str,
        expires_at: datetime | None,
        activate_workspace_on_success: bool,
    ) -> None:
        if user_id is None:
            return

        self._pending_password_reset = PendingPasswordReset(
            user_id=user_id,
            identifier=identifier,
            expires_at=expires_at,
            activate_workspace_on_success=activate_workspace_on_success,
        )
        if activate_workspace_on_success and expires_at is not None:
            expiry = expires_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            self.password_reset_identity_label.setText(
                f"Signed in as {identifier}. Update the temporary password before accessing the application. Session expires at {expiry}."
            )
            self.password_reset_cancel_button.setText("Sign out")
            status_message = "Password reset is mandatory for this account."
            tone = "warning"
        else:
            self.password_reset_identity_label.setText(
                f"Identity verified for {identifier}. Choose a new password, then return to sign in."
            )
            self.password_reset_cancel_button.setText("Back to Sign in")
            status_message = "Verification complete. Set a new password to finish recovery."
            tone = "success"
        self.new_password_input.clear()
        self.confirm_password_input.clear()
        self._set_status_label(
            self.password_reset_status_label,
            status_message,
            tone=tone,
        )
        self._pages.setCurrentWidget(self.password_reset_page)
        self.setWindowTitle(f"{self._app_name} | Password Reset")
        self.new_password_input.setFocus()

    def _submit_password_reset(self) -> None:
        if self._pending_password_reset is None:
            return

        new_password = self.new_password_input.text()
        confirmation = self.confirm_password_input.text()
        if not new_password or not confirmation:
            self._set_status_label(
                self.password_reset_status_label,
                "Enter and confirm the new password.",
                tone="error",
            )
            return
        if new_password != confirmation:
            self._set_status_label(
                self.password_reset_status_label,
                "The new password and confirmation do not match.",
                tone="error",
            )
            return

        try:
            self._auth_service.reset_password(
                user_id=self._pending_password_reset.user_id,
                new_password=new_password,
            )
        except ValueError as exc:
            self._set_status_label(
                self.password_reset_status_label,
                str(exc),
                tone="error",
            )
            return

        pending_reset = self._pending_password_reset
        self._pending_password_reset = None
        self.new_password_input.clear()
        self.confirm_password_input.clear()
        self._set_status_label(self.password_reset_status_label, "", tone="success")
        if pending_reset.activate_workspace_on_success and pending_reset.expires_at is not None:
            self._activate_workspace(
                identifier=pending_reset.identifier,
                expires_at=pending_reset.expires_at,
                password_reset_required=False,
            )
            self._render_authorized_navigation()
            self._navigate(self._default_route_key(), clear_notice=False)
            self._set_status_label(
                self.workspace_notice,
                "Password updated. Authenticated successfully. Routes now render inside the same session-aware workspace.",
                tone="success",
            )
            return

        self._return_to_login(
            identifier=pending_reset.identifier,
            message="Password updated. Sign in with your new password.",
            tone="success",
        )

    def _activate_workspace(
        self,
        *,
        identifier: str,
        expires_at: datetime,
        password_reset_required: bool,
    ) -> None:
        self._session_state = SessionState(
            user_id=self._current_user_id or "",
            identifier=identifier,
            expires_at=expires_at,
            password_reset_required=password_reset_required,
        )

        expiry = expires_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.workspace_heading.setText(f"{self._app_name} Workspace")
        self.workspace_summary_label.setText(
            f"Signed in as {identifier}. Session expires at {expiry}."
        )
        self.session_badge_label.setText(
            f"User ID: {self._current_user_id}\n"
            f"Identity: {identifier}\n"
            f"Expiry: {expiry}"
        )
        self.home_session_label.setText(
            f"Current user: {identifier}\n"
            f"User ID: {self._current_user_id}\n"
            f"Session expiry: {expiry}"
        )
        if password_reset_required:
            self._set_status_label(
                self.workspace_notice,
                "Authenticated successfully. Password reset is required before continuing.",
                tone="warning",
            )
        else:
            self._set_status_label(
                self.workspace_notice,
                "Authenticated successfully. Routes now render inside the same session-aware workspace.",
                tone="success",
            )
        self._pages.setCurrentWidget(self.workspace_page)

    def _render_authorized_navigation(self) -> None:
        if self._current_user_id is None:
            return

        self._sync_admin_route_presentation()
        context = self._authorization_service.build_context(self._current_user_id)
        nav_checks = {
            "home": "nav:home",
            "admin": "nav:admin",
            "billing": "nav:billing",
        }

        for route_key, permission in nav_checks.items():
            button = self._nav_buttons[route_key]
            is_allowed = self._authorization_guard.can(permission=permission, context=context)
            button.setEnabled(is_allowed)
            button.setToolTip("" if is_allowed else f"Access denied by default for {permission}")

        report_allowed = self._authorization_guard.can(permission="report:run", context=context)
        self.report_button.setEnabled(report_allowed)
        self.report_button.setToolTip(
            "" if report_allowed else "Access denied by default for report:run"
        )

    def _default_route_key(self) -> str:
        for route_key in ("home", "admin", "billing"):
            if self._nav_buttons[route_key].isEnabled():
                return route_key
        return "home"

    def _navigate(self, route_key: str, *, clear_notice: bool = True) -> None:
        if self._session_state is None or route_key not in self._route_config:
            return

        button = self._nav_buttons.get(route_key)
        if button is not None and not button.isEnabled():
            return

        route = self._route_config[route_key]
        self._active_route = route_key
        self.route_stack.setCurrentWidget(route["widget"])
        self.page_title_label.setText(route["title"])
        route_subtitle = route["subtitle"]
        self.page_subtitle_label.setText(route_subtitle)
        self.page_subtitle_label.setVisible(bool(route_subtitle))
        self.setWindowTitle(f"{self._app_name} | {route['title']}")

        for key, nav_button in self._nav_buttons.items():
            nav_button.setChecked(key == route_key)

        if clear_notice:
            self._set_status_label(self.workspace_notice, "", tone="success")

    def _run_operational_report(self) -> None:
        if self._current_user_id is None:
            return

        try:
            report_status = self._reporting_service.run_operational_report(
                user_id=self._current_user_id
            )
        except AuthorizationDeniedError as exc:
            self._set_status_label(self.workspace_notice, str(exc), tone="error")
            return

        self._set_status_label(self.workspace_notice, report_status, tone="success")

    def _logout(self) -> None:
        self._current_user_id = None
        self._session_state = None
        self._pending_password_reset = None
        self.admin_page.set_current_user_id(None)
        self.identifier_input.clear()
        self.password_input.clear()
        self.recovery_identifier_input.clear()
        self.recovery_contact_input.clear()
        self.new_password_input.clear()
        self.confirm_password_input.clear()
        self._set_status_label(self.recovery_status_label, "", tone="success")
        self._set_status_label(self.password_reset_status_label, "", tone="success")
        self._set_loading(False)
        self._reset_workspace_state()
        self._return_to_login(
            message="Signed out. Enter your credentials to start a new session.",
            tone="success",
        )

    def _reset_workspace_state(self) -> None:
        self._sync_admin_route_presentation()
        self.workspace_heading.setText("Secure workspace")
        self.workspace_summary_label.setText(
            "Sign in to unlock navigation and protected actions."
        )
        self.session_badge_label.setText("No active session")
        self.home_session_label.setText(
            "Sign in to populate session metadata and route-aware workspace details."
        )
        self.page_title_label.setText("Home")
        self.page_subtitle_label.setText("Use the navigation rail to move through the app.")
        self.page_subtitle_label.show()
        self.route_stack.setCurrentWidget(self.home_page)
        self._set_status_label(self.workspace_notice, "", tone="success")
        for button in self._nav_buttons.values():
            button.setEnabled(False)
            button.setChecked(False)
        self.report_button.setEnabled(False)
        self._active_route = "home"

    def _reload_admin_ui(self) -> None:
        if self._app_env.lower() != "development" or self._session_state is None:
            return

        try:
            admin_management_module = importlib.import_module(
                "app.desktop_shell.ui.admin_management"
            )
            admin_management_module = importlib.reload(admin_management_module)
            reloaded_admin_page = admin_management_module.AccessControlWorkspace(
                current_user_id=self._current_user_id,
                audit_service=self._audit_service,
                audit_review_service=self._audit_review_service,
                user_management_service=self._admin_user_management_service,
                parent=self,
            )
        except Exception as exc:
            self._set_status_label(
                self.workspace_notice,
                f"Admin UI reload failed: {exc}",
                tone="error",
            )
            return

        previous_admin_page = self.admin_page
        previous_route = self._active_route
        self.admin_page = reloaded_admin_page
        self._route_config["admin"]["widget"] = self.admin_page

        admin_index = self.route_stack.indexOf(previous_admin_page)
        self.route_stack.insertWidget(admin_index, self.admin_page)
        self.route_stack.removeWidget(previous_admin_page)
        previous_admin_page.deleteLater()

        self._sync_admin_route_presentation()
        self._render_authorized_navigation()
        self._navigate(previous_route, clear_notice=False)
        self._set_status_label(
            self.workspace_notice,
            "Admin UI reloaded from source for development testing.",
            tone="success",
        )

    def _sync_admin_route_presentation(self) -> None:
        is_superadmin = (
            self._current_user_id is not None
            and self._admin_user_management_service.role_name_for_user(self._current_user_id) == "Superadmin"
        )
        if is_superadmin:
            self.nav_admin_button.setText("Superadmin Dashboard")
            self._route_config["admin"]["title"] = "Superadmin Dashboard"
            self._route_config["admin"]["subtitle"] = ""
            return

        self.nav_admin_button.setText("Admin Console")
        self._route_config["admin"]["title"] = "Admin Console"
        self._route_config["admin"]["subtitle"] = (
            "Manage users, roles, permissions, and audit review in the same workspace."
        )

    def _set_loading(self, is_loading: bool) -> None:
        self._is_loading = is_loading
        self.identifier_input.setDisabled(is_loading)
        self.password_input.setDisabled(is_loading)
        self.login_button.setDisabled(is_loading)
        self.reset_button.setDisabled(is_loading)
        self.login_button.setText("Signing in..." if is_loading else "Sign in")

    def _set_status_label(self, label: QLabel, message: str, *, tone: str) -> None:
        label.setText(message)
        label.setVisible(bool(message))
        label.setProperty("tone", tone)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def _open_forgot_password_page(self) -> None:
        self._pending_password_reset = None
        self.password_input.clear()
        self.recovery_identifier_input.setText(self.identifier_input.text().strip())
        self.recovery_contact_input.clear()
        self._set_status_label(self.validation_label, "", tone="success")
        self._set_status_label(self.recovery_status_label, "", tone="success")
        self._pages.setCurrentWidget(self.forgot_password_page)
        self.setWindowTitle(f"{self._app_name} | Recover Access")
        if self.recovery_identifier_input.text():
            self.recovery_contact_input.setFocus()
        else:
            self.recovery_identifier_input.setFocus()

    def _return_to_login_from_recovery(self) -> None:
        identifier = self.recovery_identifier_input.text().strip()
        self._pending_password_reset = None
        self._set_status_label(self.recovery_status_label, "", tone="success")
        self._return_to_login(identifier=identifier)

    def _verify_password_recovery(self) -> None:
        identifier = self.recovery_identifier_input.text().strip()
        recovery_contact = self.recovery_contact_input.text().strip()
        if not identifier or not recovery_contact:
            self._set_status_label(
                self.recovery_status_label,
                "Enter the identifier and one registered contact value.",
                tone="error",
            )
            return

        result = self._auth_service.begin_password_recovery(
            identifier=identifier,
            recovery_contact=recovery_contact,
            correlation_id=str(uuid4()),
        )
        if not result.success or result.user_id is None or result.username is None:
            self._set_status_label(
                self.recovery_status_label,
                "We could not verify those recovery details.",
                tone="error",
            )
            return

        self._begin_password_reset(
            user_id=result.user_id,
            identifier=result.username,
            expires_at=None,
            activate_workspace_on_success=False,
        )

    def _cancel_password_reset(self) -> None:
        if self._pending_password_reset is None:
            self._return_to_login()
            return
        if self._pending_password_reset.activate_workspace_on_success:
            self._logout()
            return

        identifier = self._pending_password_reset.identifier
        self._pending_password_reset = None
        self.new_password_input.clear()
        self.confirm_password_input.clear()
        self._set_status_label(self.password_reset_status_label, "", tone="success")
        self._return_to_login(identifier=identifier)

    def _return_to_login(
        self,
        *,
        identifier: str = "",
        message: str = "",
        tone: str = "success",
    ) -> None:
        self.identifier_input.setText(identifier)
        self.password_input.clear()
        self._set_status_label(self.validation_label, message, tone=tone)
        self._pages.setCurrentWidget(self.login_page)
        self.setWindowTitle(f"{self._app_name} | Secure Access")
        if identifier:
            self.password_input.setFocus()
        else:
            self.identifier_input.setFocus()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #efe8df;
            }
            QWidget#LoginPage, QWidget#RecoveryPage, QWidget#WorkspacePage {
                background-color: #efe8df;
            }
            QFrame#SplashPanel {
                background: qlineargradient(
                    x1: 0,
                    y1: 0,
                    x2: 1,
                    y2: 1,
                    stop: 0 #174c4f,
                    stop: 0.55 #1f6a5e,
                    stop: 1 #c17b37
                );
                border-radius: 28px;
            }
            QLabel#HeroEyebrow, QLabel#WorkspaceEyebrow, QLabel#CardEyebrow {
                font-size: 11px;
                font-weight: 700;
                color: #fdf2e6;
            }
            QLabel#HeroTitle {
                font-size: 40px;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#HeroSubtitle, QLabel#HeroFooter {
                font-size: 15px;
                color: #f6efe6;
            }
            QFrame#FeatureCard {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 18px;
            }
            QLabel#FeatureTitle {
                font-size: 15px;
                font-weight: 700;
                color: #ffffff;
            }
            QLabel#FeatureDetail {
                font-size: 13px;
                color: #f1e7d8;
            }
            QFrame#LoginCard, QFrame#WorkspaceSidebar, QFrame#WorkspaceContent {
                background-color: #fbf8f4;
                border: 1px solid #d7c9b8;
                border-radius: 24px;
            }
            QFrame#WorkspaceBanner {
                background-color: #174c4f;
                border-radius: 24px;
            }
            QFrame#InnerCard {
                background-color: #f3ece4;
                border: 1px solid #dccdbd;
                border-radius: 18px;
            }
            QLabel#CardEyebrow {
                color: #8b5a2b;
            }
            QLabel#CardTitle, QLabel#WorkspaceTitle {
                font-size: 30px;
                font-weight: 700;
                color: #1f2933;
            }
            QLabel#FormLabel {
                font-size: 13px;
                font-weight: 700;
                color: #3d3025;
            }
            QLabel#CardSubtitle, QLabel#CardHelper, QLabel#SectionCopy, QLabel#PageSubtitle {
                font-size: 14px;
                color: #52606d;
            }
            QLabel#WorkspaceTitle, QLabel#WorkspaceSubtitle {
                color: #ffffff;
            }
            QLabel#SectionTitle, QLabel#PageTitle {
                font-size: 18px;
                font-weight: 700;
                color: #1f2933;
            }
            QLabel#PageTitle {
                font-size: 28px;
            }
            QLabel#PageEyebrow, QLabel#SidebarHeading {
                font-size: 11px;
                font-weight: 700;
                color: #8b5a2b;
            }
            QLabel#SessionBadge {
                background-color: rgba(255, 255, 255, 0.14);
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 16px;
                color: #fdf2e6;
                font-size: 13px;
                font-weight: 600;
                padding: 12px 14px;
            }
            QLabel#StatusMessage {
                padding: 10px 12px;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#StatusMessage[tone="error"] {
                background-color: #fef3f2;
                color: #b42318;
                border: 1px solid #fecdca;
            }
            QLabel#StatusMessage[tone="warning"] {
                background-color: #fffaeb;
                color: #b54708;
                border: 1px solid #fedf89;
            }
            QLabel#StatusMessage[tone="success"] {
                background-color: #ecfdf3;
                color: #027a48;
                border: 1px solid #abefc6;
            }
            QLineEdit {
                min-height: 42px;
                padding: 0 12px;
                border: 1px solid #cbb9a3;
                border-radius: 12px;
                background-color: #ffffff;
                color: #1f2933;
                selection-background-color: #174c4f;
            }
            QLineEdit::placeholder {
                color: #8a7f73;
            }
            QLineEdit:focus {
                border: 1px solid #8b5a2b;
            }
            QPushButton {
                min-width: 120px;
                padding: 0 18px;
                border: none;
                border-radius: 14px;
                background-color: #174c4f;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1f5f63;
            }
            QPushButton:disabled {
                background-color: #b7a492;
                color: #f4ede6;
            }
            QPushButton#LinkButton {
                background-color: transparent;
                color: #174c4f;
                padding: 0;
            }
            QPushButton#LinkButton:hover {
                background-color: transparent;
                color: #0f3739;
            }
            QPushButton#NavButton {
                background-color: transparent;
                border: 1px solid #d7c9b8;
                color: #1f2933;
                padding-left: 16px;
                text-align: left;
            }
            QPushButton#NavButton:hover {
                background-color: #efe5d9;
            }
            QPushButton#NavButton:checked {
                background-color: #174c4f;
                border: 1px solid #174c4f;
                color: #ffffff;
            }
            QPushButton#NavButton:disabled {
                background-color: #ede7df;
                border: 1px solid #ede7df;
                color: #8a7f73;
            }
            QPushButton#ActionButton {
                background-color: #8b5a2b;
            }
            QPushButton#ActionButton:hover {
                background-color: #774b22;
            }
            QPushButton#SecondaryButton {
                background-color: #efe5d9;
                color: #1f2933;
            }
            QPushButton#SecondaryButton:hover {
                background-color: #e6d7c5;
            }
            """
        )
