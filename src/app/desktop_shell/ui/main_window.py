from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable
from uuid import uuid4

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.admin.services import (
    AdminStoreRecord,
    AdminUserManagementService,
    StaffMemberProfile,
    StoreDashboardContext,
    StoreStaffRow,
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
from app.desktop_shell.i18n import SUPPORTED_LANGUAGES
from app.desktop_shell.ui.action_logging import install_action_logging, log_ui_action
from app.desktop_shell.ui.manager_customer import StoreManagerCustomerDashboardScreen
from app.desktop_shell.ui.manager_orders import StoreManagerOrdersManagementScreen
from app.desktop_shell.ui.manager_work import StoreManagerWorkManagementScreen
from app.operations.services import (
    ItemRow,
    OperationsService,
    WorkerPaymentHistoryRow,
    WorkerPaymentItemRow,
)
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


class StoreProfileHomeScreen(QWidget):
    def __init__(
        self,
        *,
        user_management_service: AdminUserManagementService,
        on_store_updated: Callable[[AdminStoreRecord], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_management_service = user_management_service
        self._on_store_updated = on_store_updated
        self._current_user_id: str | None = None
        self._store_record: AdminStoreRecord | None = None
        self._editable = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        profile_card = QFrame()
        profile_card.setObjectName("InnerCard")
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(22, 22, 22, 22)
        profile_layout.setSpacing(14)

        title = QLabel("Store Information")
        title.setObjectName("SectionTitle")
        self.copy_label = QLabel(
            "Only address and store contact information can be updated here."
        )
        self.copy_label.setObjectName("SectionCopy")
        self.copy_label.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)

        self.store_name_input = self._build_readonly_input()
        self.store_code_input = self._build_readonly_input()
        self.city_input = self._build_readonly_input()
        self.status_input = self._build_readonly_input()
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Store address")
        self.contact_info_input = QLineEdit()
        self.contact_info_input.setPlaceholderText("Store contact information")

        form.addRow(self._form_label("Store name"), self.store_name_input)
        form.addRow(self._form_label("Store code"), self.store_code_input)
        form.addRow(self._form_label("City"), self.city_input)
        form.addRow(self._form_label("Status"), self.status_input)
        form.addRow(self._form_label("Address"), self.address_input)
        form.addRow(self._form_label("Contact information"), self.contact_info_input)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.save_button = QPushButton("Save Store Details")
        self.save_button.setObjectName("ActionButton")
        self.save_button.setMinimumHeight(44)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("StatusMessage")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.hide()

        profile_layout.addWidget(title)
        profile_layout.addWidget(self.copy_label)
        profile_layout.addLayout(form)
        profile_layout.addWidget(self.feedback_label)
        profile_layout.addLayout(actions)

        future_card = QFrame()
        future_card.setObjectName("InnerCard")
        future_layout = QVBoxLayout(future_card)
        future_layout.setContentsMargins(22, 22, 22, 22)
        future_layout.setSpacing(10)

        future_title = QLabel("Reserved Space")
        future_title.setObjectName("SectionTitle")
        future_copy = QLabel(
            "This area is intentionally left open for future store-specific enhancements."
        )
        future_copy.setObjectName("SectionCopy")
        future_copy.setWordWrap(True)

        future_layout.addWidget(future_title)
        future_layout.addWidget(future_copy)
        future_layout.addStretch(1)

        root.addWidget(profile_card)
        root.addWidget(future_card)
        root.addStretch(1)

        self.cancel_button.clicked.connect(self._restore_current_values)
        self.save_button.clicked.connect(self._save_store_profile)
        self.clear_context()

    def set_store_context(
        self,
        *,
        current_user_id: str | None,
        store_record: AdminStoreRecord,
        editable: bool,
    ) -> None:
        self._current_user_id = current_user_id
        self._store_record = store_record
        self._editable = editable
        self._set_status("", tone="success")

        self.store_name_input.setText(store_record.store_name)
        self.store_code_input.setText(store_record.store_code)
        self.city_input.setText(store_record.city)
        self.status_input.setText(store_record.status)
        self.address_input.setText(store_record.address)
        self.contact_info_input.setText(store_record.contact_info)
        self.address_input.setReadOnly(not editable)
        self.contact_info_input.setReadOnly(not editable)
        self.address_input.setClearButtonEnabled(editable)
        self.contact_info_input.setClearButtonEnabled(editable)
        self.cancel_button.setVisible(editable)
        self.save_button.setVisible(editable)
        self.copy_label.setText(
            "Only address and store contact information can be updated here."
            if editable
            else "Store profile details are shown here for reference. This session cannot change them."
        )

    def clear_context(self) -> None:
        self._current_user_id = None
        self._store_record = None
        self._editable = False
        for widget in (
            self.store_name_input,
            self.store_code_input,
            self.city_input,
            self.status_input,
            self.address_input,
            self.contact_info_input,
        ):
            widget.clear()
        self.address_input.setReadOnly(True)
        self.contact_info_input.setReadOnly(True)
        self.address_input.setClearButtonEnabled(False)
        self.contact_info_input.setClearButtonEnabled(False)
        self.cancel_button.hide()
        self.save_button.hide()
        self._set_status("", tone="success")

    def _build_readonly_input(self) -> QLineEdit:
        widget = QLineEdit()
        widget.setReadOnly(True)
        return widget

    def _form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        return label

    def _restore_current_values(self) -> None:
        if self._store_record is None:
            return
        self.address_input.setText(self._store_record.address)
        self.contact_info_input.setText(self._store_record.contact_info)
        self._set_status("Reverted unsaved changes.", tone="success")

    def _save_store_profile(self) -> None:
        if self._store_record is None or not self._editable:
            return

        try:
            updated_record = self._user_management_service.update_store_profile_for_user(
                actor_user_id=self._current_user_id,
                address=self.address_input.text(),
                contact_info=self.contact_info_input.text(),
            )
        except ValueError as exc:
            self._set_status(str(exc), tone="error")
            return

        self._store_record = updated_record
        self.address_input.setText(updated_record.address)
        self.contact_info_input.setText(updated_record.contact_info)
        self._set_status("Store details updated successfully.", tone="success")
        if self._on_store_updated is not None:
            self._on_store_updated(updated_record)

    def _set_status(self, message: str, *, tone: str) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(bool(message))
        self.feedback_label.setProperty("tone", tone)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.update()


class StoreAdminDashboardScreen(QWidget):
    def __init__(
        self,
        *,
        user_management_service: AdminUserManagementService,
        operations_service: OperationsService,
        on_manager_language_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_management_service = user_management_service
        self._operations_service = operations_service
        self._on_manager_language_changed = on_manager_language_changed
        self._current_user_id: str | None = None
        self._store_context: StoreDashboardContext | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        self.staff_table = self._build_table(("Full Name", "Role"))
        self.items_table = self._build_table(("Item Name", "Cost"))
        self.language_settings_panel = self._build_language_settings_panel()
        self.future_b_placeholder = self._build_placeholder(
            "Reserved for additional store-specific enhancements."
        )

        self.staff_card = self._build_card(
            title="Store Staff",
            subtitle="Store users assigned to this location.",
            content_widget=self.staff_table,
        )
        self.items_card = self._build_card(
            title="Store Items",
            subtitle="Current item catalog and item costs for this store.",
            content_widget=self.items_table,
        )
        self.language_settings_card = self._build_card(
            title="Manager Screen Language",
            subtitle="Choose the language used only on manager screens for this store.",
            content_widget=self.language_settings_panel,
        )
        self.future_b_card = self._build_card(
            title="Future Use",
            subtitle="Reserved area for future enhancements.",
            content_widget=self.future_b_placeholder,
        )

        grid.addWidget(self.staff_card, 0, 0)
        grid.addWidget(self.items_card, 0, 1)
        grid.addWidget(self.language_settings_card, 1, 0)
        grid.addWidget(self.future_b_card, 1, 1)

        root.addLayout(grid)
        root.addStretch(1)

        self.clear_context()
        self.save_language_button.clicked.connect(self._save_manager_language)

    def set_context(
        self,
        *,
        current_user_id: str | None,
        store_context: StoreDashboardContext,
    ) -> None:
        self._current_user_id = current_user_id
        self._store_context = store_context
        self.refresh_data()

    def clear_context(self) -> None:
        self._current_user_id = None
        self._store_context = None
        self._set_table_rows(
            self.staff_table,
            rows=(),
            empty_message="Store staff will appear here after users are created.",
        )
        self._set_table_rows(
            self.items_table,
            rows=(),
            empty_message="Store items will appear here after they are created.",
        )
        self.manager_language_combo.setCurrentIndex(0)
        self.save_language_button.setEnabled(False)
        self.language_feedback_label.hide()

    def refresh_data(self) -> None:
        if self._store_context is None:
            self.clear_context()
            return

        staff_rows = self._user_management_service.list_store_staff(
            actor_user_id=self._current_user_id
        )
        item_rows = self._operations_service.list_items(store_id=self._store_context.store_id)
        self._sync_language_controls()

        self._set_table_rows(
            self.staff_table,
            rows=tuple((row.full_name, row.role_name) for row in staff_rows),
            empty_message="Create store staff to populate this table.",
        )
        self._set_table_rows(
            self.items_table,
            rows=tuple((row.item_name, f"INR {row.cost:,.2f}") for row in item_rows),
            empty_message="Create items to populate this table.",
            numeric_columns={1},
        )

    def _build_language_settings_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.manager_language_combo = QComboBox()
        self.manager_language_combo.setMinimumHeight(38)
        for code, label in SUPPORTED_LANGUAGES:
            self.manager_language_combo.addItem(label, code)
        form.addRow(self._form_label("Language"), self.manager_language_combo)

        self.save_language_button = QPushButton("Save Language")
        self.save_language_button.setObjectName("ActionButton")
        self.save_language_button.setMinimumHeight(40)

        self.language_feedback_label = QLabel("")
        self.language_feedback_label.setObjectName("StatusMessage")
        self.language_feedback_label.setWordWrap(True)
        self.language_feedback_label.hide()

        layout.addLayout(form)
        layout.addWidget(self.save_language_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.language_feedback_label)
        layout.addStretch(1)
        return panel

    def _form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        return label

    def _sync_language_controls(self) -> None:
        if self._store_context is None:
            return
        self.manager_language_combo.blockSignals(True)
        for index in range(self.manager_language_combo.count()):
            if self.manager_language_combo.itemData(index) == self._store_context.manager_language_code:
                self.manager_language_combo.setCurrentIndex(index)
                break
        self.manager_language_combo.blockSignals(False)
        self.save_language_button.setEnabled(True)
        self.language_feedback_label.hide()

    def _save_manager_language(self) -> None:
        if self._current_user_id is None:
            return
        language_code = self.manager_language_combo.currentData()
        if not isinstance(language_code, str):
            language_code = "en"
        try:
            self._store_context = self._user_management_service.update_manager_language_for_store_admin(
                actor_user_id=self._current_user_id,
                language_code=language_code,
            )
        except ValueError as exc:
            self._set_language_feedback(str(exc), tone="error")
            return

        self._set_language_feedback("Manager screen language updated.", tone="success")
        if self._on_manager_language_changed is not None:
            self._on_manager_language_changed()

    def _set_language_feedback(self, message: str, *, tone: str) -> None:
        self.language_feedback_label.setText(message)
        self.language_feedback_label.setProperty("tone", tone)
        self.language_feedback_label.style().unpolish(self.language_feedback_label)
        self.language_feedback_label.style().polish(self.language_feedback_label)
        self.language_feedback_label.setVisible(bool(message))

    def _build_card(
        self,
        *,
        title: str,
        subtitle: str,
        content_widget: QWidget,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("InnerCard")
        card.setMinimumHeight(250)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("SectionCopy")
        subtitle_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(content_widget, stretch=1)
        return card

    def _build_table(self, headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setObjectName("DashboardTable")
        table.setHorizontalHeaderLabels(list(headers))
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setCornerButtonEnabled(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(38)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setMinimumSectionSize(120)
        return table

    def _build_placeholder(self, message: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(0)
        label = QLabel(message)
        label.setObjectName("DashboardPlaceholder")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
        return widget

    def _set_table_rows(
        self,
        table: QTableWidget,
        *,
        rows: tuple[tuple[str, str], ...],
        empty_message: str,
        numeric_columns: set[int] | None = None,
    ) -> None:
        numeric_columns = numeric_columns or set()
        table.setSortingEnabled(False)
        table.clearSpans()
        table.clearContents()

        if not rows:
            table.setRowCount(1)
            table.setSpan(0, 0, 1, table.columnCount())
            empty_item = QTableWidgetItem(empty_message)
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            empty_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(0, 0, empty_item)
            for column_index in range(1, table.columnCount()):
                table.setItem(0, column_index, QTableWidgetItem(""))
            return

        table.setRowCount(len(rows))
        for row_index, row_values in enumerate(rows):
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                alignment = (
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if column_index in numeric_columns
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                item.setTextAlignment(alignment)
                table.setItem(row_index, column_index, item)


class StaffMemberEditorDialog(QDialog):
    def __init__(
        self,
        *,
        role_options: tuple[str, ...],
        created_by_name: str,
        profile: StaffMemberProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._role_options = role_options
        self.setModal(True)
        self.setWindowTitle("Add Staff Member" if profile is None else "Staff Member Details")
        self.setMinimumSize(820, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_copy = QVBoxLayout()
        header_copy.setSpacing(6)

        title = QLabel("Add Staff Member" if profile is None else "Edit Staff Member")
        title.setObjectName("SectionTitle")
        copy = QLabel(
            "Capture the staff member profile in one screen. Select one or more store staff roles."
        )
        copy.setObjectName("SectionCopy")
        copy.setWordWrap(True)

        header_copy.addWidget(title)
        header_copy.addWidget(copy)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.save_button = QPushButton("Add Staff Member" if profile is None else "Update Staff Member")
        self.save_button.setObjectName("ActionButton")
        self.save_button.setMinimumHeight(42)
        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.save_button)

        header_layout.addLayout(header_copy, stretch=1)
        header_layout.addLayout(action_layout)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("StatusMessage")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.hide()

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        identity_card = QFrame()
        identity_card.setObjectName("InnerCard")
        identity_layout = QVBoxLayout(identity_card)
        identity_layout.setContentsMargins(18, 18, 18, 18)
        identity_layout.setSpacing(12)

        identity_title = QLabel("Identity")
        identity_title.setObjectName("SectionTitle")

        identity_form = QFormLayout()
        identity_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        identity_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        identity_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        identity_form.setHorizontalSpacing(12)
        identity_form.setVerticalSpacing(12)

        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Enter full name")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        self.contact_number_input = QLineEdit()
        self.contact_number_input.setPlaceholderText("Enter contact number")
        self.speciality_input = QLineEdit()
        self.speciality_input.setPlaceholderText("Alterations, finishing, packaging, dispatch...")

        identity_form.addRow(self._form_label("Full name"), self.full_name_input)
        identity_form.addRow(self._form_label("Username"), self.username_input)
        identity_form.addRow(self._form_label("Contact number"), self.contact_number_input)
        identity_form.addRow(self._form_label("Speciality"), self.speciality_input)

        identity_layout.addWidget(identity_title)
        identity_layout.addLayout(identity_form)

        assignment_card = QFrame()
        assignment_card.setObjectName("InnerCard")
        assignment_layout = QVBoxLayout(assignment_card)
        assignment_layout.setContentsMargins(18, 18, 18, 18)
        assignment_layout.setSpacing(12)

        assignment_title = QLabel("Assignment")
        assignment_title.setObjectName("SectionTitle")

        assignment_form = QFormLayout()
        assignment_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        assignment_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        assignment_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        assignment_form.setHorizontalSpacing(12)
        assignment_form.setVerticalSpacing(12)

        self.joining_date_input = QDateEdit()
        self.joining_date_input.setCalendarPopup(True)
        self.joining_date_input.setDisplayFormat("yyyy-MM-dd")
        self.joining_date_input.setMinimumHeight(42)
        self.role_checks: dict[str, QCheckBox] = {}
        roles_panel = QWidget()
        roles_layout = QVBoxLayout(roles_panel)
        roles_layout.setContentsMargins(0, 0, 0, 0)
        roles_layout.setSpacing(6)
        for role_name in role_options:
            role_check = QCheckBox(role_name)
            role_check.setMinimumHeight(28)
            self.role_checks[role_name] = role_check
            roles_layout.addWidget(role_check)
        roles_layout.addStretch(1)
        self.created_by_input = QLineEdit()
        self.created_by_input.setReadOnly(True)

        assignment_form.addRow(self._form_label("Joining date"), self.joining_date_input)
        assignment_form.addRow(self._form_label("Roles"), roles_panel)
        assignment_form.addRow(self._form_label("Created by"), self.created_by_input)

        assignment_layout.addWidget(assignment_title)
        assignment_layout.addLayout(assignment_form)
        assignment_layout.addStretch(1)

        content_layout.addWidget(identity_card, stretch=1)
        content_layout.addWidget(assignment_card, stretch=1)

        root.addLayout(header_layout)
        root.addWidget(self.feedback_label)
        root.addLayout(content_layout)

        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._attempt_accept)

        self._populate(profile=profile, created_by_name=created_by_name)

    def payload(self) -> dict[str, object]:
        selected_date = self.joining_date_input.date().toPython()
        joining_date = datetime(
            selected_date.year,
            selected_date.month,
            selected_date.day,
            tzinfo=timezone.utc,
        )
        return {
            "full_name": self.full_name_input.text().strip(),
            "username": self.username_input.text().strip(),
            "contact_number": self.contact_number_input.text().strip(),
            "speciality": self.speciality_input.text().strip(),
            "joining_date": joining_date,
            "role_names": [
                role_name
                for role_name, checkbox in self.role_checks.items()
                if checkbox.isChecked()
            ],
        }

    def set_feedback(self, message: str, *, tone: str) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(bool(message))
        self.feedback_label.setProperty("tone", tone)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.update()

    def _populate(self, *, profile: StaffMemberProfile | None, created_by_name: str) -> None:
        self.set_feedback("", tone="success")
        default_role = self._role_options[0] if self._role_options else "Worker"
        for checkbox in self.role_checks.values():
            checkbox.setChecked(False)
        if profile is None:
            self.full_name_input.clear()
            self.username_input.clear()
            self.username_input.setReadOnly(False)
            self.contact_number_input.clear()
            self.speciality_input.clear()
            self.joining_date_input.setDate(QDate.currentDate())
            if default_role in self.role_checks:
                self.role_checks[default_role].setChecked(True)
            self.created_by_input.setText(created_by_name)
            return

        self.full_name_input.setText(profile.full_name)
        self.username_input.setText(profile.username)
        self.username_input.setReadOnly(True)
        self.contact_number_input.setText(profile.contact_number)
        self.speciality_input.setText(profile.speciality)
        self.joining_date_input.setDate(
            QDate(
                profile.joining_date.year,
                profile.joining_date.month,
                profile.joining_date.day,
            )
        )
        selected_roles = profile.roles or ((profile.role_name,) if profile.role_name else ())
        for role_name in selected_roles:
            if role_name in self.role_checks:
                self.role_checks[role_name].setChecked(True)
        self.created_by_input.setText(profile.created_by_name or created_by_name)

    def _attempt_accept(self) -> None:
        payload = self.payload()
        if not payload["full_name"]:
            self.set_feedback("Full name is required.", tone="error")
            return
        if not payload["username"]:
            self.set_feedback("Username is required.", tone="error")
            return
        if not payload["contact_number"]:
            self.set_feedback("Contact number is required.", tone="error")
            return
        if not payload["role_names"]:
            self.set_feedback("Select at least one role.", tone="error")
            return
        self.accept()

    def _form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        return label


class StoreStaffCreateScreen(QWidget):
    TABLE_HEADERS = (
        "Full Name",
        "Contact Number",
        "Speciality",
        "Joining Date",
        "Role",
        "Username",
        "Created By",
    )

    def __init__(
        self,
        *,
        user_management_service: AdminUserManagementService,
        on_staff_created: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_management_service = user_management_service
        self._on_staff_created = on_staff_created
        self._current_user_id: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(12)

        self.add_staff_button = QPushButton("Add Staff Member")
        self.add_staff_button.setObjectName("ActionButton")
        self.add_staff_button.setMinimumHeight(44)

        toolbar.addWidget(self.add_staff_button, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addStretch(1)

        self.staff_feedback_label = QLabel("")
        self.staff_feedback_label.setObjectName("StatusMessage")
        self.staff_feedback_label.setWordWrap(True)
        self.staff_feedback_label.hide()

        self.staff_password_label = QLabel("")
        self.staff_password_label.setObjectName("SectionCopy")
        self.staff_password_label.setWordWrap(True)
        self.staff_password_label.hide()

        table_card = QFrame()
        table_card.setObjectName("InnerCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(22, 22, 22, 22)
        table_layout.setSpacing(12)

        title = QLabel("Store Staff")
        title.setObjectName("SectionTitle")
        copy = QLabel(
            "Double-click a row to review or update that staff member. This table only shows staff members created by the signed-in store admin."
        )
        copy.setObjectName("SectionCopy")
        copy.setWordWrap(True)

        self.staff_table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.staff_table.setObjectName("DashboardTable")
        self.staff_table.setHorizontalHeaderLabels(list(self.TABLE_HEADERS))
        self.staff_table.setAlternatingRowColors(True)
        self.staff_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.staff_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.staff_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.staff_table.setSortingEnabled(True)
        self.staff_table.setShowGrid(False)
        self.staff_table.verticalHeader().setVisible(False)
        self.staff_table.verticalHeader().setDefaultSectionSize(38)
        self.staff_table.horizontalHeader().setStretchLastSection(False)
        self.staff_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.staff_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.staff_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.staff_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.staff_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.staff_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.staff_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        table_layout.addWidget(title)
        table_layout.addWidget(copy)
        table_layout.addWidget(self.staff_table, stretch=1)

        root.addLayout(toolbar)
        root.addWidget(self.staff_feedback_label)
        root.addWidget(self.staff_password_label)
        root.addWidget(table_card, stretch=1)

        self.add_staff_button.clicked.connect(self._open_add_staff_dialog)
        self.staff_table.cellDoubleClicked.connect(self._open_staff_dialog_for_row)
        self.set_current_user_id(None)

    def set_current_user_id(self, current_user_id: str | None) -> None:
        self._current_user_id = current_user_id
        self._set_feedback("", tone="success")
        self.staff_password_label.clear()
        self.staff_password_label.hide()
        self.refresh_data()

    def refresh_data(self) -> None:
        role_options = self._role_options()
        self.add_staff_button.setEnabled(bool(role_options) and self._current_user_id is not None)
        self.staff_table.setSortingEnabled(False)
        self.staff_table.clearSpans()
        self.staff_table.clearContents()

        staff_rows = self._user_management_service.list_store_staff(
            actor_user_id=self._current_user_id,
            created_by_actor_only=False,
        )
        if not staff_rows:
            self.staff_table.setRowCount(1)
            self.staff_table.setSpan(0, 0, 1, self.staff_table.columnCount())
            empty_item = QTableWidgetItem(
                "No staff members created yet. Use 'Add Staff Member' to create the first one."
            )
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.staff_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.staff_table.columnCount()):
                self.staff_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.staff_table.setRowCount(len(staff_rows))
        for row_index, staff_row in enumerate(staff_rows):
            row_values = (
                staff_row.full_name,
                staff_row.contact_number,
                staff_row.speciality or "Not set",
                staff_row.joining_date.astimezone(timezone.utc).strftime("%Y-%m-%d"),
                staff_row.role_name,
                staff_row.username,
                staff_row.created_by_name or "Current admin",
            )
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setData(Qt.ItemDataRole.UserRole, staff_row.user_id)
                self.staff_table.setItem(row_index, column_index, item)
        self.staff_table.setSortingEnabled(True)
        self.staff_table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def _role_options(self) -> tuple[str, ...]:
        return tuple(
            role_name
            for role_name in self._user_management_service.available_roles_for_actor(self._current_user_id)
            if role_name in {"Manager", "Accountant", "Worker"}
        )

    def _open_add_staff_dialog(self) -> None:
        if self._current_user_id is None:
            return
        role_options = self._role_options()
        if not role_options:
            self._set_feedback("This account cannot create store staff.", tone="error")
            return

        creator_name = self._user_management_service.display_name_for_user(self._current_user_id)
        dialog = StaffMemberEditorDialog(
            role_options=role_options,
            created_by_name=creator_name,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.payload()
            try:
                result = self._user_management_service.create_staff_member(
                    actor_user_id=self._current_user_id,
                    username=str(payload["username"]),
                    full_name=str(payload["full_name"]),
                    contact_number=str(payload["contact_number"]),
                    speciality=str(payload["speciality"]),
                    joining_date=payload["joining_date"],  # type: ignore[arg-type]
                    role_names=list(payload["role_names"]),  # type: ignore[arg-type]
                )
            except ValueError as exc:
                dialog.set_feedback(str(exc), tone="error")
                continue

            self._set_feedback("Staff member created successfully.", tone="success")
            self.staff_password_label.setText(
                f"Temporary password for {result.username}: {result.temporary_password}"
            )
            self.staff_password_label.show()
            self.refresh_data()
            if self._on_staff_created is not None:
                self._on_staff_created()
            break

    def _open_staff_dialog_for_row(self, row: int, _column: int) -> None:
        user_item = self.staff_table.item(row, 0)
        if user_item is None:
            return
        user_id = user_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(user_id, str):
            return
        if self._current_user_id is None:
            return

        profile = self._user_management_service.get_staff_member_profile(
            actor_user_id=self._current_user_id,
            user_id=user_id,
        )
        if profile is None:
            self._set_feedback("The selected staff member could not be loaded.", tone="error")
            return

        dialog = StaffMemberEditorDialog(
            role_options=self._role_options(),
            created_by_name=profile.created_by_name,
            profile=profile,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.payload()
            try:
                self._user_management_service.update_staff_member(
                    actor_user_id=self._current_user_id,
                    user_id=user_id,
                    full_name=str(payload["full_name"]),
                    contact_number=str(payload["contact_number"]),
                    speciality=str(payload["speciality"]),
                    joining_date=payload["joining_date"],  # type: ignore[arg-type]
                    role_names=list(payload["role_names"]),  # type: ignore[arg-type]
                )
            except ValueError as exc:
                dialog.set_feedback(str(exc), tone="error")
                continue

            self._set_feedback("Staff member updated successfully.", tone="success")
            self.staff_password_label.clear()
            self.staff_password_label.hide()
            self.refresh_data()
            if self._on_staff_created is not None:
                self._on_staff_created()
            break

    def _set_feedback(self, message: str, *, tone: str) -> None:
        self.staff_feedback_label.setText(message)
        self.staff_feedback_label.setVisible(bool(message))
        self.staff_feedback_label.setProperty("tone", tone)
        self.staff_feedback_label.style().unpolish(self.staff_feedback_label)
        self.staff_feedback_label.style().polish(self.staff_feedback_label)
        self.staff_feedback_label.update()


class ItemEditorDialog(QDialog):
    def __init__(
        self,
        *,
        store_name: str,
        item_row: ItemRow | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item_row = item_row
        self.setModal(True)
        self.setWindowTitle("Add Item" if item_row is None else "Item Details")
        self.setMinimumSize(760, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_copy = QVBoxLayout()
        header_copy.setSpacing(6)

        title = QLabel("Add Item" if item_row is None else "Edit Item")
        title.setObjectName("SectionTitle")
        copy = QLabel(
            "Capture the item details in one screen. Changes update only the active store catalog."
        )
        copy.setObjectName("SectionCopy")
        copy.setWordWrap(True)

        header_copy.addWidget(title)
        header_copy.addWidget(copy)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.save_button = QPushButton("Add Item" if item_row is None else "Update Item")
        self.save_button.setObjectName("ActionButton")
        self.save_button.setMinimumHeight(42)
        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.save_button)

        header_layout.addLayout(header_copy, stretch=1)
        header_layout.addLayout(action_layout)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("StatusMessage")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.hide()

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        details_card = QFrame()
        details_card.setObjectName("InnerCard")
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(18, 18, 18, 18)
        details_layout.setSpacing(12)

        details_title = QLabel("Catalog Details")
        details_title.setObjectName("SectionTitle")

        details_form = QFormLayout()
        details_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        details_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        details_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        details_form.setHorizontalSpacing(12)
        details_form.setVerticalSpacing(12)

        self.item_name_input = QLineEdit()
        self.item_name_input.setPlaceholderText("Enter item name")
        self.cost_input = QLineEdit()
        self.cost_input.setPlaceholderText("0.00")
        self.making_charges_input = QLineEdit()
        self.making_charges_input.setPlaceholderText("0.00")
        self.store_input = QLineEdit()
        self.store_input.setReadOnly(True)

        details_form.addRow(self._form_label("Item name"), self.item_name_input)
        details_form.addRow(self._form_label("Cost"), self.cost_input)
        details_form.addRow(self._form_label("Making charges"), self.making_charges_input)
        details_form.addRow(self._form_label("Store"), self.store_input)

        details_layout.addWidget(details_title)
        details_layout.addLayout(details_form)
        details_layout.addStretch(1)

        metadata_card = QFrame()
        metadata_card.setObjectName("InnerCard")
        metadata_layout = QVBoxLayout(metadata_card)
        metadata_layout.setContentsMargins(18, 18, 18, 18)
        metadata_layout.setSpacing(12)

        metadata_title = QLabel("Record Metadata")
        metadata_title.setObjectName("SectionTitle")

        metadata_form = QFormLayout()
        metadata_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        metadata_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        metadata_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        metadata_form.setHorizontalSpacing(12)
        metadata_form.setVerticalSpacing(12)

        self.created_on_input = QLineEdit()
        self.created_on_input.setReadOnly(True)
        self.updated_on_input = QLineEdit()
        self.updated_on_input.setReadOnly(True)

        metadata_form.addRow(self._form_label("Created on"), self.created_on_input)
        metadata_form.addRow(self._form_label("Last updated"), self.updated_on_input)

        metadata_layout.addWidget(metadata_title)
        metadata_layout.addLayout(metadata_form)
        metadata_layout.addStretch(1)

        content_layout.addWidget(details_card, stretch=1)
        content_layout.addWidget(metadata_card, stretch=1)

        root.addLayout(header_layout)
        root.addWidget(self.feedback_label)
        root.addLayout(content_layout)

        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._attempt_accept)

        self._populate(store_name=store_name, item_row=item_row)

    def payload(self) -> dict[str, str]:
        return {
            "item_name": self.item_name_input.text().strip(),
            "cost_text": self.cost_input.text().strip(),
            "making_charges_text": self.making_charges_input.text().strip(),
        }

    def set_feedback(self, message: str, *, tone: str) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(bool(message))
        self.feedback_label.setProperty("tone", tone)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.update()

    def _populate(self, *, store_name: str, item_row: ItemRow | None) -> None:
        self.set_feedback("", tone="success")
        self.store_input.setText(store_name)
        if item_row is None:
            self.item_name_input.clear()
            self.cost_input.clear()
            self.making_charges_input.clear()
            self.created_on_input.setText("Will be set when the item is created")
            self.updated_on_input.setText("Will be set when the item is created")
            return

        self.item_name_input.setText(item_row.item_name)
        self.cost_input.setText(f"{item_row.cost:.2f}")
        self.making_charges_input.setText(f"{item_row.making_charges:.2f}")
        self.created_on_input.setText(item_row.created_on.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        self.updated_on_input.setText(item_row.updated_on.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    def _attempt_accept(self) -> None:
        payload = self.payload()
        if not payload["item_name"]:
            self.set_feedback("Item name is required.", tone="error")
            return
        if not payload["cost_text"]:
            self.set_feedback("Cost is required.", tone="error")
            return
        if not payload["making_charges_text"]:
            self.set_feedback("Making charges are required.", tone="error")
            return
        try:
            cost = Decimal(payload["cost_text"])
            making_charges = Decimal(payload["making_charges_text"])
        except (InvalidOperation, ValueError):
            self.set_feedback("Enter valid numeric cost and making charges.", tone="error")
            return
        if cost < Decimal("0.00"):
            self.set_feedback("Item cost cannot be negative.", tone="error")
            return
        if making_charges < Decimal("0.00"):
            self.set_feedback("Making charges cannot be negative.", tone="error")
            return
        self.accept()

    def _form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        return label


class StoreItemsCreateScreen(QWidget):
    TABLE_HEADERS = (
        "Item Name",
        "Cost",
        "Making Charges",
        "Created On",
        "Updated On",
    )

    def __init__(
        self,
        *,
        user_management_service: AdminUserManagementService,
        operations_service: OperationsService,
        on_item_created: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_management_service = user_management_service
        self._operations_service = operations_service
        self._on_item_created = on_item_created
        self._current_user_id: str | None = None
        self._store_context: StoreDashboardContext | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(12)

        self.add_item_button = QPushButton("Add Item")
        self.add_item_button.setObjectName("ActionButton")
        self.add_item_button.setMinimumHeight(44)

        toolbar.addWidget(self.add_item_button, alignment=Qt.AlignmentFlag.AlignLeft)
        toolbar.addStretch(1)

        self.item_feedback_label = QLabel("")
        self.item_feedback_label.setObjectName("StatusMessage")
        self.item_feedback_label.setWordWrap(True)
        self.item_feedback_label.hide()

        table_card = QFrame()
        table_card.setObjectName("InnerCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(22, 22, 22, 22)
        table_layout.setSpacing(12)

        title = QLabel("Store Items")
        title.setObjectName("SectionTitle")
        copy = QLabel(
            "Double-click a row to review or update that item. This table only shows items for the active store."
        )
        copy.setObjectName("SectionCopy")
        copy.setWordWrap(True)

        self.items_table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.items_table.setObjectName("DashboardTable")
        self.items_table.setHorizontalHeaderLabels(list(self.TABLE_HEADERS))
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.setSortingEnabled(True)
        self.items_table.setShowGrid(False)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.verticalHeader().setDefaultSectionSize(38)
        self.items_table.horizontalHeader().setStretchLastSection(False)
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        table_layout.addWidget(title)
        table_layout.addWidget(copy)
        table_layout.addWidget(self.items_table, stretch=1)

        root.addLayout(toolbar)
        root.addWidget(self.item_feedback_label)
        root.addWidget(table_card, stretch=1)

        self.add_item_button.clicked.connect(self._open_add_item_dialog)
        self.items_table.cellDoubleClicked.connect(self._open_item_dialog_for_row)
        self.set_current_user_id(None)

    def set_current_user_id(self, current_user_id: str | None) -> None:
        self._current_user_id = current_user_id
        self._store_context = self._user_management_service.get_store_dashboard_context_for_user(
            current_user_id
        )
        self._set_feedback("", tone="success")
        self.refresh_data()

    def refresh_data(self) -> None:
        self.items_table.setSortingEnabled(False)
        self.items_table.clearSpans()
        self.items_table.clearContents()
        if self._store_context is None:
            self.add_item_button.setEnabled(False)
            self.items_table.setRowCount(1)
            self.items_table.setSpan(0, 0, 1, self.items_table.columnCount())
            empty_item = QTableWidgetItem(
                "Sign in with a store admin account to manage items for a store."
            )
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.items_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.items_table.columnCount()):
                self.items_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.add_item_button.setEnabled(True)
        item_rows = self._operations_service.list_items(store_id=self._store_context.store_id)
        if not item_rows:
            self.items_table.setRowCount(1)
            self.items_table.setSpan(0, 0, 1, self.items_table.columnCount())
            empty_item = QTableWidgetItem(
                "No items created yet. Use 'Add Item' to create the first one."
            )
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.items_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.items_table.columnCount()):
                self.items_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.items_table.setRowCount(len(item_rows))
        for row_index, item_row in enumerate(item_rows):
            row_values = (
                item_row.item_name,
                f"INR {item_row.cost:,.2f}",
                f"INR {item_row.making_charges:,.2f}",
                item_row.created_on.astimezone(timezone.utc).strftime("%Y-%m-%d"),
                item_row.updated_on.astimezone(timezone.utc).strftime("%Y-%m-%d"),
            )
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setData(Qt.ItemDataRole.UserRole, item_row.item_id)
                alignment = (
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if column_index in {1, 2}
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                item.setTextAlignment(alignment)
                self.items_table.setItem(row_index, column_index, item)
        self.items_table.setSortingEnabled(True)
        self.items_table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def _open_add_item_dialog(self) -> None:
        if self._store_context is None:
            self._set_feedback("Store context is required before creating an item.", tone="error")
            return

        dialog = ItemEditorDialog(
            store_name=self._store_context.store_name,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.payload()
            try:
                self._operations_service.create_item(
                    store_id=self._store_context.store_id,
                    item_name=payload["item_name"],
                    cost=Decimal(payload["cost_text"]),
                    making_charges=Decimal(payload["making_charges_text"]),
                )
            except ValueError as exc:
                dialog.set_feedback(str(exc), tone="error")
                continue

            self._set_feedback("Item created successfully.", tone="success")
            self.refresh_data()
            if self._on_item_created is not None:
                self._on_item_created()
            break

    def _open_item_dialog_for_row(self, row: int, _column: int) -> None:
        if self._store_context is None:
            return
        item_cell = self.items_table.item(row, 0)
        if item_cell is None:
            return
        item_id = item_cell.data(Qt.ItemDataRole.UserRole)
        if not isinstance(item_id, str):
            return

        item_row = self._operations_service.get_item(
            store_id=self._store_context.store_id,
            item_id=item_id,
        )
        if item_row is None:
            self._set_feedback("The selected item could not be loaded.", tone="error")
            return

        dialog = ItemEditorDialog(
            store_name=self._store_context.store_name,
            item_row=item_row,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.payload()
            try:
                self._operations_service.update_item(
                    store_id=self._store_context.store_id,
                    item_id=item_id,
                    item_name=payload["item_name"],
                    cost=Decimal(payload["cost_text"]),
                    making_charges=Decimal(payload["making_charges_text"]),
                )
            except ValueError as exc:
                dialog.set_feedback(str(exc), tone="error")
                continue

            self._set_feedback("Item updated successfully.", tone="success")
            self.refresh_data()
            if self._on_item_created is not None:
                self._on_item_created()
            break

    def _set_feedback(self, message: str, *, tone: str) -> None:
        self.item_feedback_label.setText(message)
        self.item_feedback_label.setVisible(bool(message))
        self.item_feedback_label.setProperty("tone", tone)
        self.item_feedback_label.style().unpolish(self.item_feedback_label)
        self.item_feedback_label.style().polish(self.item_feedback_label)
        self.item_feedback_label.update()


class StorePaymentsScreen(QWidget):
    UNPAID_TABLE_HEADERS = (
        "Customer-item",
        "Item Status",
        "Worker Name",
        "Updated On",
        "Making Charges",
    )
    PAID_TABLE_HEADERS = (
        "Customer-item",
        "Item Status",
        "Worker Name",
        "Updated On",
        "Maker's Pay Status",
    )
    HISTORY_HEADERS = ("Date", "Amount", "Method", "Notes")

    def __init__(
        self,
        *,
        user_management_service: AdminUserManagementService,
        operations_service: OperationsService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_management_service = user_management_service
        self._operations_service = operations_service
        self._current_user_id: str | None = None
        self._store_context: StoreDashboardContext | None = None
        self._workers: tuple[StoreStaffRow, ...] = ()
        self._rows: tuple[WorkerPaymentItemRow, ...] = ()
        self._metric_rows: tuple[WorkerPaymentItemRow, ...] = ()
        self._payment_history: tuple[WorkerPaymentHistoryRow, ...] = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        metrics_row = QHBoxLayout()
        metrics_row.setContentsMargins(0, 0, 0, 0)
        metrics_row.setSpacing(12)

        self.worker_filter = QComboBox()
        self.worker_filter.setMinimumHeight(36)
        self.worker_filter.setMinimumWidth(190)
        metrics_row.addWidget(self._worker_filter_metric())

        self.total_items_value = QLabel("0")
        self.ready_items_value = QLabel("0")
        self.making_charges_value = QLabel("INR 0.00")
        self.advance_paid_value = QLabel("INR 0.00")
        self.dues_value = QLabel("INR 0.00")
        metrics_row.addWidget(self._metric_card("TOTAL ITEMS", self.total_items_value))
        metrics_row.addWidget(self._metric_card("READY ITEMS", self.ready_items_value))
        self.making_charges_card = self._metric_card("MAKING CHARGES", self.making_charges_value)
        self.advance_paid_card = self._metric_card("TOTAL PAID", self.advance_paid_value)
        self.dues_card = self._metric_card("DUES", self.dues_value)
        metrics_row.addWidget(self.making_charges_card)
        metrics_row.addWidget(self.advance_paid_card)
        metrics_row.addWidget(self.dues_card)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(16)

        left_section = QWidget()
        left_layout = QVBoxLayout(left_section)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        right_section = QWidget()
        right_section.setObjectName("PaymentsDetailSection")
        right_layout = QVBoxLayout(right_section)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        form_title = QLabel("Worker Payment")
        form_title.setObjectName("SectionTitle")

        payment_form = QVBoxLayout()
        payment_form.setContentsMargins(0, 0, 0, 0)
        payment_form.setSpacing(10)
        self.worker_payment_amount_input = QLineEdit()
        self.worker_payment_amount_input.setObjectName("WorkerPaymentCompactInput")
        self.worker_payment_amount_input.setPlaceholderText("Enter amount")
        self.worker_payment_amount_input.setFixedHeight(34)
        self.worker_payment_amount_input.setMinimumWidth(0)
        self.worker_payment_amount_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.worker_payment_method_combo = QComboBox()
        self.worker_payment_method_combo.setObjectName("WorkerPaymentCompactInput")
        self.worker_payment_method_combo.addItems(("Cash", "UPI", "Card", "Bank Transfer", "Other"))
        self.worker_payment_method_combo.setFixedHeight(34)
        self.worker_payment_method_combo.setMinimumWidth(0)
        self.worker_payment_method_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.worker_payment_notes_input = QLineEdit()
        self.worker_payment_notes_input.setObjectName("WorkerPaymentCompactInput")
        self.worker_payment_notes_input.setPlaceholderText("Payment note")
        self.worker_payment_notes_input.setFixedHeight(34)
        self.worker_payment_notes_input.setMinimumWidth(0)
        self.worker_payment_notes_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        amount_method_row = QHBoxLayout()
        amount_method_row.setContentsMargins(0, 0, 0, 0)
        amount_method_row.setSpacing(8)
        amount_method_row.addWidget(
            self._payment_field("Paying Amount", self.worker_payment_amount_input),
            stretch=1,
        )
        amount_method_row.addWidget(
            self._payment_field("Payment Method", self.worker_payment_method_combo),
            stretch=1,
        )
        payment_form.addLayout(amount_method_row)
        payment_form.addWidget(self._payment_field("Notes", self.worker_payment_notes_input))

        self.record_worker_payment_button = QPushButton("Record Payment")
        self.record_worker_payment_button.setObjectName("ActionButton")
        self.record_worker_payment_button.setMinimumHeight(40)
        self.record_worker_payment_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.worker_payment_feedback = QLabel("")
        self.worker_payment_feedback.setObjectName("StatusMessage")
        self.worker_payment_feedback.setWordWrap(True)
        self.worker_payment_feedback.hide()

        history_title = QLabel("Payment History")
        history_title.setObjectName("SectionTitle")
        self.worker_payment_history_table = QTableWidget(0, len(self.HISTORY_HEADERS))
        self.worker_payment_history_table.setObjectName("PaymentsFlatTable")
        self.worker_payment_history_table.setHorizontalHeaderLabels(list(self.HISTORY_HEADERS))
        self.worker_payment_history_table.setAlternatingRowColors(True)
        self.worker_payment_history_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.worker_payment_history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.worker_payment_history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.worker_payment_history_table.setShowGrid(False)
        self.worker_payment_history_table.setMinimumHeight(180)
        self.worker_payment_history_table.verticalHeader().setVisible(False)
        self.worker_payment_history_table.verticalHeader().setDefaultSectionSize(28)
        self.worker_payment_history_table.horizontalHeader().setStretchLastSection(False)
        self.worker_payment_history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.worker_payment_history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.worker_payment_history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.worker_payment_history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        right_layout.addWidget(form_title)
        right_layout.addLayout(payment_form)
        right_layout.addWidget(self.record_worker_payment_button)
        right_layout.addWidget(self.worker_payment_feedback)
        right_layout.addWidget(history_title)
        right_layout.addWidget(self.worker_payment_history_table, stretch=1)

        self.payments_table = QTableWidget(0, len(self.UNPAID_TABLE_HEADERS))
        self.payments_table.setObjectName("PaymentsFlatTable")
        self.payments_table.setHorizontalHeaderLabels(list(self.UNPAID_TABLE_HEADERS))
        self.payments_table.setAlternatingRowColors(True)
        self.payments_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.payments_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.payments_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.payments_table.setShowGrid(False)
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.verticalHeader().setDefaultSectionSize(32)
        self.payments_table.horizontalHeader().setStretchLastSection(False)
        self.payments_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.payments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.payments_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.payments_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.payments_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self.payments_table, stretch=1)
        content_row.addWidget(left_section, stretch=6)
        content_row.addWidget(right_section, stretch=4)

        root.addLayout(metrics_row)
        root.addLayout(content_row, stretch=1)

        self.worker_filter.currentIndexChanged.connect(lambda _index=0: self.refresh_data())
        self.record_worker_payment_button.clicked.connect(self._record_worker_payment)
        self.clear_context()

    def set_context(
        self,
        *,
        current_user_id: str | None,
        store_context: StoreDashboardContext,
    ) -> None:
        self._current_user_id = current_user_id
        self._store_context = store_context
        self.refresh_data()

    def clear_context(self) -> None:
        self._current_user_id = None
        self._store_context = None
        self._workers = ()
        self._rows = ()
        self._metric_rows = ()
        self._payment_history = ()
        self._set_worker_filter()
        self._set_metrics((), ())
        self._set_table_rows(())
        self._set_payment_history_rows(())
        self._refresh_payment_form_state()

    def refresh_data(self) -> None:
        if self._store_context is None:
            self.clear_context()
            return
        selected_worker_id = self.worker_filter.currentData()
        worker_id = selected_worker_id if isinstance(selected_worker_id, str) else ""
        self._workers = self._user_management_service.list_store_workers(
            store_id=self._store_context.store_id
        )
        self._set_worker_filter(selected_worker_id=worker_id)
        self._payment_history = self._operations_service.list_worker_payment_history_for_store(
            store_id=self._store_context.store_id,
            worker_id=worker_id,
        )
        if worker_id:
            self._operations_service.sync_worker_maker_pay_status_for_store(
                store_id=self._store_context.store_id,
                worker_id=worker_id,
            )
        self._metric_rows = self._operations_service.list_worker_payment_items_for_store(
            store_id=self._store_context.store_id,
            worker_id=worker_id,
            include_paid=True,
        )
        show_pay_status = self._should_show_maker_pay_status()
        if show_pay_status:
            self._rows = ()
        else:
            self._rows = self._operations_service.list_worker_payment_items_for_store(
                store_id=self._store_context.store_id,
                worker_id=worker_id,
            )
        self._set_metrics(self._rows, self._metric_rows)
        self._set_table_rows(self._rows)
        self._set_payment_history_rows(self._payment_history)
        self._refresh_payment_form_state()

    def _set_worker_filter(self, *, selected_worker_id: str = "") -> None:
        self.worker_filter.blockSignals(True)
        self.worker_filter.clear()
        self.worker_filter.addItem("All Workers", "")
        for worker in self._workers:
            self.worker_filter.addItem(worker.full_name, worker.user_id)
        for index in range(self.worker_filter.count()):
            if self.worker_filter.itemData(index) == selected_worker_id:
                self.worker_filter.setCurrentIndex(index)
                break
        self.worker_filter.blockSignals(False)

    def _set_metrics(
        self,
        count_rows: tuple[WorkerPaymentItemRow, ...],
        money_rows: tuple[WorkerPaymentItemRow, ...],
    ) -> None:
        paid_amount = sum((row.paid_amount for row in self._payment_history), Decimal("0.00"))
        making_charges = sum((row.making_charges for row in money_rows), Decimal("0.00"))
        dues_amount = making_charges - paid_amount
        has_selected_worker = self._selected_worker() is not None
        self.total_items_value.setText(str(len(count_rows)))
        self.ready_items_value.setText(str(sum(1 for row in count_rows if row.item_status == "READY")))
        self.making_charges_value.setText(self._format_currency(making_charges))
        self.advance_paid_value.setText(self._format_currency(paid_amount))
        self.dues_value.setText("No Dues" if dues_amount == Decimal("0.00") else self._format_currency(dues_amount))
        is_settled = making_charges == paid_amount
        self.making_charges_card.setVisible(has_selected_worker and not is_settled)
        self.advance_paid_card.setVisible(has_selected_worker and not is_settled)
        self.dues_card.setVisible(has_selected_worker)

    def _should_show_maker_pay_status(self) -> bool:
        if self._selected_worker() is None:
            return False
        paid_amount = sum((row.paid_amount for row in self._payment_history), Decimal("0.00"))
        making_charges = sum((row.making_charges for row in self._metric_rows), Decimal("0.00"))
        return making_charges - paid_amount == Decimal("0.00")

    def _configure_payments_table_columns(self, *, show_pay_status: bool) -> None:
        headers = self.PAID_TABLE_HEADERS if show_pay_status else self.UNPAID_TABLE_HEADERS
        if self.payments_table.columnCount() != len(headers):
            self.payments_table.setColumnCount(len(headers))
        self.payments_table.setHorizontalHeaderLabels(list(headers))
        self.payments_table.horizontalHeader().setStretchLastSection(False)
        self.payments_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column_index in range(1, len(headers)):
            self.payments_table.horizontalHeader().setSectionResizeMode(
                column_index,
                QHeaderView.ResizeMode.ResizeToContents,
            )

    def _set_table_rows(self, rows: tuple[WorkerPaymentItemRow, ...]) -> None:
        show_pay_status = self._should_show_maker_pay_status()
        self._configure_payments_table_columns(show_pay_status=show_pay_status)
        self.payments_table.clearSpans()
        self.payments_table.clearContents()
        if not rows:
            self.payments_table.setRowCount(1)
            self.payments_table.setSpan(0, 0, 1, self.payments_table.columnCount())
            empty_message = (
                "Maker's pay is PAID. No unpaid READY items to display."
                if show_pay_status
                else "No payment items available for the selected worker."
            )
            empty_item = QTableWidgetItem(empty_message)
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.payments_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.payments_table.columnCount()):
                self.payments_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.payments_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                f"{row.customer_name}/{row.item_name}",
                row.item_status,
                row.worker_name,
                self._format_date(row.updated_on),
            )
            if show_pay_status:
                values = values + (row.maker_pay_status or "PAID",)
            else:
                values = values + (f"INR {row.making_charges:,.2f}",)
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                alignment = (
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if column_index == 4
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                item.setTextAlignment(alignment)
                self.payments_table.setItem(row_index, column_index, item)

    def _set_payment_history_rows(self, rows: tuple[WorkerPaymentHistoryRow, ...]) -> None:
        self.worker_payment_history_table.clearSpans()
        self.worker_payment_history_table.clearContents()
        if not rows:
            self.worker_payment_history_table.setRowCount(1)
            self.worker_payment_history_table.setSpan(
                0,
                0,
                1,
                self.worker_payment_history_table.columnCount(),
            )
            empty_item = QTableWidgetItem("No worker payment history found.")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.worker_payment_history_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.worker_payment_history_table.columnCount()):
                self.worker_payment_history_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.worker_payment_history_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                self._format_date(row.payment_date),
                self._format_currency(row.paid_amount),
                row.payment_method,
                row.notes,
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                alignment = (
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if column_index == 1
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                item.setTextAlignment(alignment)
                self.worker_payment_history_table.setItem(row_index, column_index, item)

    def _record_worker_payment(self) -> None:
        if self._store_context is None:
            return
        selected_worker = self._selected_worker()
        if selected_worker is None:
            self._set_worker_payment_feedback("Select a worker before recording payment.", tone="error")
            return

        raw_amount = self.worker_payment_amount_input.text().replace(",", "").strip()
        try:
            paid_amount = Decimal(raw_amount)
        except (InvalidOperation, ValueError):
            self._set_worker_payment_feedback("Enter a valid payment amount.", tone="error")
            return

        worker_id, worker_name = selected_worker
        try:
            self._operations_service.add_worker_payment_for_store(
                store_id=self._store_context.store_id,
                worker_id=worker_id,
                worker_name=worker_name,
                paid_amount=paid_amount,
                payment_method=self.worker_payment_method_combo.currentText(),
                notes=self.worker_payment_notes_input.text(),
                paid_by=self._current_user_id or "",
            )
        except ValueError as exc:
            self._set_worker_payment_feedback(str(exc), tone="error")
            return

        self.refresh_data()
        self._refresh_worker_payment_history(worker_id=worker_id)
        self.worker_payment_amount_input.clear()
        self.worker_payment_notes_input.clear()
        self._set_worker_payment_feedback("Worker payment recorded.", tone="success")

    def _refresh_worker_payment_history(self, *, worker_id: str) -> None:
        if self._store_context is None:
            self._payment_history = ()
            self._set_payment_history_rows(())
            return
        self._payment_history = self._operations_service.list_worker_payment_history_for_store(
            store_id=self._store_context.store_id,
            worker_id=worker_id,
        )
        self._set_payment_history_rows(self._payment_history)
        self._set_metrics(self._rows, self._metric_rows)

    def _selected_worker(self) -> tuple[str, str] | None:
        worker_id = self.worker_filter.currentData()
        if not isinstance(worker_id, str) or not worker_id:
            return None
        worker = next((row for row in self._workers if row.user_id == worker_id), None)
        return worker_id, worker.full_name if worker is not None else self.worker_filter.currentText().strip()

    def _refresh_payment_form_state(self) -> None:
        has_worker = self._selected_worker() is not None
        for widget in (
            self.worker_payment_amount_input,
            self.worker_payment_method_combo,
            self.worker_payment_notes_input,
            self.record_worker_payment_button,
        ):
            widget.setEnabled(has_worker)
        if not has_worker:
            self.worker_payment_amount_input.clear()
            self.worker_payment_notes_input.clear()

    def _set_worker_payment_feedback(self, message: str, *, tone: str) -> None:
        self.worker_payment_feedback.setText(message)
        self.worker_payment_feedback.setVisible(bool(message))
        self.worker_payment_feedback.setProperty("tone", tone)
        self.worker_payment_feedback.style().unpolish(self.worker_payment_feedback)
        self.worker_payment_feedback.style().polish(self.worker_payment_feedback)
        self.worker_payment_feedback.update()

    def _form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        return label

    def _payment_field(self, label_text: str, field: QWidget) -> QWidget:
        container = QWidget()
        container.setMinimumWidth(0)
        container.setMinimumHeight(48)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = self._form_label(label_text)
        label.setObjectName("WorkerPaymentCompactLabel")
        label.setFixedHeight(12)
        layout.addWidget(label)
        layout.addWidget(field)
        return container

    def _format_date(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d")

    def _format_currency(self, value: Decimal) -> str:
        amount = Decimal(value).quantize(Decimal("0.01"))
        if amount < Decimal("0.00"):
            return f"INR -{abs(amount):,.2f}"
        return f"INR {amount:,.2f}"

    def _worker_filter_metric(self) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(6)
        layout.addWidget(self.worker_filter)
        label = QLabel("WORKER")
        label.setObjectName("MetricTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return card

    def _metric_card(self, title: str, value_label: QLabel) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(6)
        value_label.setObjectName("MetricValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        layout.addWidget(title_label)
        return card


class MainWindow(QMainWindow):
    FOOTER_TEXT = "Assembled @ EnTech Garage, Pune | enatech.garage.gmail.com (c) 2026 "

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
        operations_service: OperationsService,
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
        self._operations_service = operations_service
        self._current_user_id: str | None = None
        self._session_state: SessionState | None = None
        self._pending_password_reset: PendingPasswordReset | None = None
        self._store_dashboard_context: StoreDashboardContext | None = None
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

        self.footer_label = QLabel(self.FOOTER_TEXT)
        self.footer_label.setObjectName("FooterLabel")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setWordWrap(True)

        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._pages, stretch=1)
        central_layout.addWidget(self.footer_label)
        self.setCentralWidget(central)

        self._apply_styles()
        self._reset_workspace_state()
        install_action_logging(self, screen="MainWindow", context=self._log_context)

    def _is_development_mode(self) -> bool:
        return self._app_env.lower() == "development"

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

        self.dev_account_combo = QComboBox()
        self.dev_account_combo.setObjectName("DevAccountSelect")
        self.dev_account_combo.currentIndexChanged.connect(self._fill_development_credentials)
        if self._is_development_mode():
            dev_account_label = QLabel("Development User")
            dev_account_label.setObjectName("FormLabel")
            self._populate_development_accounts()
            form.addRow(dev_account_label, self.dev_account_combo)
        else:
            self.dev_account_combo.hide()

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

    def _populate_development_accounts(self) -> None:
        self.dev_account_combo.blockSignals(True)
        self.dev_account_combo.clear()
        self.dev_account_combo.addItem("Select test user", None)
        for user in self._admin_user_management_service.list_users():
            profile = self._admin_user_management_service.get_user_profile(user.user_id)
            if profile is None:
                continue
            username = profile.username.strip()
            if not username:
                continue
            password = self._admin_user_management_service.default_password_for_username(username)
            role_label = ", ".join(profile.roles) if profile.roles else "User"
            self.dev_account_combo.addItem(
                f"{profile.full_name} ({username}) - {role_label}",
                (username, password),
            )
        self.dev_account_combo.blockSignals(False)

    def _fill_development_credentials(self, _index: int = 0) -> None:
        if not self._is_development_mode():
            return
        credentials = self.dev_account_combo.currentData()
        if not isinstance(credentials, tuple) or len(credentials) != 2:
            return
        username, password = credentials
        if not isinstance(username, str) or not isinstance(password, str):
            return
        self.identifier_input.setText(username)
        self.password_input.setText(password)

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

        self.workspace_eyebrow = QLabel("SESSION ACTIVE")
        self.workspace_eyebrow.setObjectName("WorkspaceEyebrow")

        self.workspace_heading = QLabel("Secure workspace")
        self.workspace_heading.setObjectName("WorkspaceTitle")

        self.workspace_summary_label = QLabel(
            "Sign in to unlock navigation and protected actions."
        )
        self.workspace_summary_label.setObjectName("WorkspaceSubtitle")
        self.workspace_summary_label.setWordWrap(True)

        banner_copy.addWidget(self.workspace_eyebrow)
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

        self.sidebar_store_card = QFrame()
        self.sidebar_store_card.setObjectName("InnerCard")
        sidebar_store_layout = QVBoxLayout(self.sidebar_store_card)
        sidebar_store_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_store_layout.setSpacing(6)

        self.sidebar_store_title = QLabel("Global Workspace")
        self.sidebar_store_title.setObjectName("SectionTitle")
        self.sidebar_store_location_label = QLabel(
            "Sign in to load the active store identity for this session."
        )
        self.sidebar_store_location_label.setObjectName("SectionCopy")
        self.sidebar_store_location_label.setWordWrap(True)
        self.sidebar_store_contact_label = QLabel("")
        self.sidebar_store_contact_label.setObjectName("SectionCopy")
        self.sidebar_store_contact_label.setWordWrap(True)

        sidebar_store_layout.addWidget(self.sidebar_store_title)
        sidebar_store_layout.addWidget(self.sidebar_store_location_label)
        sidebar_store_layout.addWidget(self.sidebar_store_contact_label)
        sidebar_layout.addWidget(self.sidebar_store_card)

        self.nav_home_button = QPushButton("Home")
        self.nav_admin_button = QPushButton("Admin Console")
        self.nav_create_staff_button = QPushButton("Create Staff")
        self.nav_create_items_button = QPushButton("Create Items")
        self.nav_orders_management_button = QPushButton("Orders Assignment")
        self.nav_work_management_button = QPushButton("Work Management")
        self.nav_billing_button = QPushButton("Payments")
        self.logout_button = QPushButton("Sign out")
        self.logout_button.setObjectName("SecondaryButton")
        self.logout_button.clicked.connect(self._logout)

        self._nav_buttons = {
            "home": self.nav_home_button,
            "admin": self.nav_admin_button,
            "create_staff": self.nav_create_staff_button,
            "create_items": self.nav_create_items_button,
            "orders_management": self.nav_orders_management_button,
            "work_management": self.nav_work_management_button,
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
        self.create_staff_page = StoreStaffCreateScreen(
            user_management_service=self._admin_user_management_service,
            on_staff_created=self._handle_store_staff_created,
            parent=self,
        )
        self.create_items_page = StoreItemsCreateScreen(
            user_management_service=self._admin_user_management_service,
            operations_service=self._operations_service,
            on_item_created=self._handle_store_item_created,
            parent=self,
        )
        self.orders_management_page = StoreManagerOrdersManagementScreen(
            user_management_service=self._admin_user_management_service,
            operations_service=self._operations_service,
            parent=self,
        )
        self.work_management_page = StoreManagerWorkManagementScreen(
            user_management_service=self._admin_user_management_service,
            operations_service=self._operations_service,
            parent=self,
        )
        self.billing_page = self._build_billing_page()

        self.route_stack.addWidget(self.home_page)
        self.route_stack.addWidget(self.admin_page)
        self.route_stack.addWidget(self.create_staff_page)
        self.route_stack.addWidget(self.create_items_page)
        self.route_stack.addWidget(self.orders_management_page)
        self.route_stack.addWidget(self.work_management_page)
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
            "create_staff": {
                "title": "Create Staff",
                "subtitle": "Create new store staff accounts for this store.",
                "widget": self.create_staff_page,
            },
            "create_items": {
                "title": "Create Items",
                "subtitle": "Create store items and keep the item catalog current.",
                "widget": self.create_items_page,
            },
            "orders_management": {
                "title": "Orders Assignment",
                "subtitle": "",
                "widget": self.orders_management_page,
            },
            "work_management": {
                "title": "Work Management",
                "subtitle": "",
                "widget": self.work_management_page,
            },
            "billing": {
                "title": "Payments",
                "subtitle": "Worker payment management will render here.",
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
        layout.setSpacing(0)

        self.home_mode_stack = QStackedWidget()

        self.superadmin_home_page = QWidget()
        superadmin_layout = QVBoxLayout(self.superadmin_home_page)
        superadmin_layout.setContentsMargins(0, 0, 0, 0)
        superadmin_layout.addStretch(1)

        self.store_home_page = StoreAdminDashboardScreen(
            user_management_service=self._admin_user_management_service,
            operations_service=self._operations_service,
            on_manager_language_changed=self._handle_manager_language_changed,
            parent=self,
        )

        self.store_manager_home_page = StoreManagerCustomerDashboardScreen(
            user_management_service=self._admin_user_management_service,
            operations_service=self._operations_service,
            parent=self,
        )

        self.store_worker_home_page = QWidget()
        worker_layout = QVBoxLayout(self.store_worker_home_page)
        worker_layout.setContentsMargins(0, 0, 0, 0)
        worker_layout.addStretch(1)

        self.default_home_page = QWidget()
        default_layout = QVBoxLayout(self.default_home_page)
        default_layout.setContentsMargins(0, 0, 0, 0)
        default_layout.setSpacing(16)

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

        store_card = QFrame()
        store_card.setObjectName("InnerCard")
        store_layout = QVBoxLayout(store_card)
        store_layout.setContentsMargins(20, 20, 20, 20)
        store_layout.setSpacing(10)

        store_title = QLabel("Store Dashboard")
        store_title.setObjectName("SectionTitle")
        self.home_store_summary_label = QLabel(
            "Sign in with a store user to load the current store identity and scoped team summary."
        )
        self.home_store_summary_label.setObjectName("SectionCopy")
        self.home_store_summary_label.setWordWrap(True)
        self.home_store_details_label = QLabel("")
        self.home_store_details_label.setObjectName("SectionCopy")
        self.home_store_details_label.setWordWrap(True)

        store_layout.addWidget(store_title)
        store_layout.addWidget(self.home_store_summary_label)
        store_layout.addWidget(self.home_store_details_label)

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

        default_layout.addWidget(report_card)
        default_layout.addWidget(store_card)
        default_layout.addWidget(session_card)
        default_layout.addStretch(1)

        self.home_mode_stack.addWidget(self.superadmin_home_page)
        self.home_mode_stack.addWidget(self.store_home_page)
        self.home_mode_stack.addWidget(self.store_manager_home_page)
        self.home_mode_stack.addWidget(self.store_worker_home_page)
        self.home_mode_stack.addWidget(self.default_home_page)
        layout.addWidget(self.home_mode_stack)
        return page

    def _build_billing_page(self) -> QWidget:
        return StorePaymentsScreen(
            user_management_service=self._admin_user_management_service,
            operations_service=self._operations_service,
            parent=self,
        )

    def _attempt_login(self) -> None:
        log_ui_action("MainWindow", "attempt_login", **self._log_context())
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
        log_ui_action("MainWindow", "submit_password_reset", **self._log_context())
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
        self._store_dashboard_context = (
            self._admin_user_management_service.get_store_dashboard_context_for_user(
                self._current_user_id
            )
        )

        expiry = expires_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self._refresh_store_scoped_shell(identifier=identifier, expiry=expiry)
        self._refresh_store_admin_views()
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

        self._sync_route_presentation()
        context = self._authorization_service.build_context(self._current_user_id)
        store_scoped_mode = self._is_store_scoped_workspace_mode()
        store_admin_mode = self._is_store_admin_mode()
        store_manager_mode = self._is_store_manager_mode()
        accountant_mode = self._has_role("Accountant")

        if store_scoped_mode:
            route_permissions = {
                "home": True,
                "admin": store_admin_mode
                and self._authorization_guard.can(permission="nav:admin", context=context),
                "create_staff": store_admin_mode and self._admin_user_management_service.can_actor_create_users(
                    self._current_user_id
                ),
                "create_items": store_admin_mode,
                "orders_management": store_manager_mode,
                "work_management": store_manager_mode,
                "billing": accountant_mode
                and self._authorization_guard.can(permission="worker:payment:view", context=context),
            }
            visible_routes = {"home"}
            if store_manager_mode:
                visible_routes.update({"orders_management", "work_management"})
            if accountant_mode:
                visible_routes.add("billing")
            if store_admin_mode:
                visible_routes.update({"admin", "create_staff", "create_items"})
        else:
            route_permissions = {
                "home": self._authorization_guard.can(permission="nav:home", context=context),
                "admin": self._authorization_guard.can(permission="nav:admin", context=context),
                "create_staff": False,
                "create_items": False,
                "orders_management": False,
                "work_management": False,
                "billing": self._authorization_guard.can(permission="nav:billing", context=context),
            }
            visible_routes = {"home", "admin", "billing"}

        for route_key, button in self._nav_buttons.items():
            is_visible = route_key in visible_routes
            button.setVisible(is_visible)
            is_allowed = route_permissions.get(route_key, False)
            button.setEnabled(is_allowed)
            if route_key == "create_staff":
                tooltip_key = "store staff creation"
            elif route_key == "create_items":
                tooltip_key = "store item creation"
            elif route_key == "orders_management":
                tooltip_key = "orders assignment"
            elif route_key == "work_management":
                tooltip_key = "work management"
            elif route_key == "billing":
                tooltip_key = "payments"
            else:
                tooltip_key = route_key
            button.setToolTip("" if is_allowed else f"Access denied for {tooltip_key}.")

        report_allowed = self._authorization_guard.can(permission="report:run", context=context)
        self.report_button.setEnabled(report_allowed)
        self.report_button.setToolTip(
            "" if report_allowed else "Access denied by default for report:run"
        )

    def _default_route_key(self) -> str:
        if (
            self._current_user_id is not None
            and self._admin_user_management_service.role_name_for_user(self._current_user_id) == "Superadmin"
            and self._nav_buttons["admin"].isEnabled()
        ):
            return "admin"
        route_order = (
            ("home", "orders_management", "work_management", "billing", "admin", "create_staff", "create_items")
            if self._is_store_scoped_workspace_mode()
            else ("home", "admin", "billing")
        )
        for route_key in route_order:
            if self._nav_buttons[route_key].isEnabled():
                return route_key
        return "home"

    def _navigate(self, route_key: str, *, clear_notice: bool = True) -> None:
        log_ui_action("MainWindow", "navigate", target_route=route_key, **self._log_context())
        if self._session_state is None or route_key not in self._route_config:
            return

        button = self._nav_buttons.get(route_key)
        if button is not None and not button.isEnabled():
            return

        route = self._route_config[route_key]
        self._active_route = route_key
        if route_key == "orders_management":
            self.orders_management_page.refresh_data()
        elif route_key == "work_management":
            self.work_management_page.refresh_data()
        elif route_key == "billing" and isinstance(self.billing_page, StorePaymentsScreen):
            self.billing_page.refresh_data()
        self.route_stack.setCurrentWidget(route["widget"])
        self.page_title_label.setText(route["title"])
        hide_route_heading = route_key in {"orders_management", "work_management"}
        self.page_eyebrow.setVisible(not hide_route_heading)
        self.page_title_label.setVisible(not hide_route_heading)
        route_subtitle = route["subtitle"]
        self.page_subtitle_label.setText(route_subtitle)
        self.page_subtitle_label.setVisible(bool(route_subtitle) and not hide_route_heading)
        self.setWindowTitle(f"{self._app_name} | {route['title']}")

        for key, nav_button in self._nav_buttons.items():
            nav_button.setChecked(key == route_key)

        if clear_notice:
            self._set_status_label(self.workspace_notice, "", tone="success")
        self._update_workspace_chrome_visibility()

    def _run_operational_report(self) -> None:
        log_ui_action("MainWindow", "run_operational_report", **self._log_context())
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
        log_ui_action("MainWindow", "logout", **self._log_context())
        self._current_user_id = None
        self._session_state = None
        self._pending_password_reset = None
        self._store_dashboard_context = None
        self.admin_page.set_current_user_id(None)
        self.create_staff_page.set_current_user_id(None)
        self.create_items_page.set_current_user_id(None)
        self.orders_management_page.clear_context()
        self.work_management_page.clear_context()
        if isinstance(self.billing_page, StorePaymentsScreen):
            self.billing_page.clear_context()
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
        self._store_dashboard_context = None
        self._sync_route_presentation()
        self.workspace_heading.setText("Secure workspace")
        self.workspace_summary_label.setText(
            "Sign in to unlock navigation and protected actions."
        )
        self.session_badge_label.setText("No active session")
        self.sidebar_store_title.setText("Global Workspace")
        self.sidebar_store_location_label.setText(
            "Sign in to load the active store identity for this session."
        )
        self.sidebar_store_contact_label.setText("")
        self.home_store_summary_label.setText(
            "Sign in with a store user to load the current store identity and scoped team summary."
        )
        self.home_store_details_label.setText("")
        self.store_home_page.clear_context()
        self.store_manager_home_page.clear_context()
        self.orders_management_page.clear_context()
        self.work_management_page.clear_context()
        if isinstance(self.billing_page, StorePaymentsScreen):
            self.billing_page.clear_context()
        self.home_mode_stack.setCurrentWidget(self.default_home_page)
        self.create_staff_page.set_current_user_id(None)
        self.create_items_page.set_current_user_id(None)
        self.home_session_label.setText(
            "Sign in to populate session metadata and route-aware workspace details."
        )
        self.page_title_label.setText("Home")
        self.page_eyebrow.show()
        self.page_title_label.show()
        self.page_subtitle_label.setText("Use the navigation rail to move through the app.")
        self.page_subtitle_label.show()
        self.route_stack.setCurrentWidget(self.home_page)
        self._set_status_label(self.workspace_notice, "", tone="success")
        for button in self._nav_buttons.values():
            button.setEnabled(False)
            button.setChecked(False)
        self.nav_home_button.show()
        self.nav_admin_button.show()
        self.nav_billing_button.show()
        self.nav_create_staff_button.hide()
        self.nav_create_items_button.hide()
        self.nav_orders_management_button.hide()
        self.nav_work_management_button.hide()
        self.report_button.setEnabled(False)
        self._active_route = "home"
        self._update_workspace_chrome_visibility()

    def _reload_admin_ui(self) -> None:
        log_ui_action("MainWindow", "reload_admin_ui", **self._log_context())
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

        self.admin_page.set_current_user_id(self._current_user_id)
        self._sync_route_presentation()
        self._render_authorized_navigation()
        self._navigate(previous_route, clear_notice=False)
        self._set_status_label(
            self.workspace_notice,
            "Admin UI reloaded from source for development testing.",
            tone="success",
        )

    def _sync_route_presentation(self) -> None:
        is_superadmin = (
            self._current_user_id is not None
            and self._admin_user_management_service.role_name_for_user(self._current_user_id) == "Superadmin"
        )
        store_admin_mode = self._is_store_admin_mode()
        store_manager_mode = self._is_store_manager_mode()
        store_worker_mode = self._is_store_worker_mode()
        has_store_scope = self._store_dashboard_context is not None
        if is_superadmin:
            self.nav_home_button.setText("Home")
            self._route_config["home"]["title"] = "Home"
            self._route_config["home"]["subtitle"] = ""
        elif store_admin_mode:
            self.nav_home_button.setText("Store Dashboard")
            self._route_config["home"]["title"] = "Store Dashboard"
            self._route_config["home"]["subtitle"] = (
                "Review store staff, items, and reserved workspace cards from this store dashboard."
            )
        elif store_manager_mode:
            self.nav_home_button.setText("Store Dashboard")
            self._route_config["home"]["title"] = "Store Dashboard"
            self._route_config["home"]["subtitle"] = ""
        elif store_worker_mode:
            worker_name = self._admin_user_management_service.display_name_for_user(self._current_user_id).strip()
            dashboard_name = f"{worker_name} Dashboard" if worker_name else "Worker Dashboard"
            self.nav_home_button.setText(dashboard_name)
            self._route_config["home"]["title"] = dashboard_name
            self._route_config["home"]["subtitle"] = ""
        elif has_store_scope:
            self.nav_home_button.setText("Store Dashboard")
            self._route_config["home"]["title"] = "Store Dashboard"
            self._route_config["home"]["subtitle"] = (
                "Review store information and keep address and contact details up to date."
            )
        else:
            self.nav_home_button.setText("Home")
            self._route_config["home"]["title"] = "Home"
            self._route_config["home"]["subtitle"] = (
                "Review the active session and run permissioned operational tasks."
            )
        if is_superadmin:
            self.nav_admin_button.setText("Superadmin Dashboard")
            self._route_config["admin"]["title"] = "Superadmin Dashboard"
            self._route_config["admin"]["subtitle"] = ""
            self._refresh_home_route_content()
            return

        self.nav_admin_button.setText("Admin Console")
        self._route_config["admin"]["title"] = "Admin Console"
        self._route_config["admin"]["subtitle"] = (
            "Manage users, roles, permissions, and audit review in the same workspace."
        )
        self.nav_create_staff_button.setText("Create Staff")
        self.nav_create_items_button.setText("Create Items")
        self.nav_orders_management_button.setText("Orders Assignment")
        self.nav_work_management_button.setText("Work Management")
        self.nav_billing_button.setText("Payments")
        self._route_config["billing"]["title"] = "Payments"
        self._route_config["billing"]["subtitle"] = ""
        self._refresh_home_route_content()

    def _refresh_store_scoped_shell(self, *, identifier: str, expiry: str) -> None:
        store_context = self._store_dashboard_context
        if store_context is None:
            self.workspace_heading.setText(f"{self._app_name} Workspace")
            self.workspace_summary_label.setText(
                f"Signed in as {identifier}. Session expires at {expiry}."
            )
            self.session_badge_label.setText(
                f"User ID: {self._current_user_id}\n"
                f"Identity: {identifier}\n"
                f"Expiry: {expiry}"
            )
            self.home_store_summary_label.setText(
                "This account is not linked to a specific store. Global workspace routes remain available based on permissions."
            )
            self.home_store_details_label.setText("")
            self.home_session_label.setText(
                f"Current user: {identifier}\n"
                f"User ID: {self._current_user_id}\n"
                f"Session expiry: {expiry}"
            )
            self.sidebar_store_title.setText("Global Workspace")
            self.sidebar_store_location_label.setText(
                "This session is not tied to a store record."
            )
            self.sidebar_store_contact_label.setText("")
            return

        location_line = store_context.address or store_context.city
        self.workspace_heading.setText(store_context.store_name)
        self.workspace_summary_label.setText(
            f"{location_line} | {store_context.contact_info}\n"
            f"Signed in as {identifier}. Session expires at {expiry}."
        )
        self.session_badge_label.setText(
            f"Store: {store_context.store_name} ({store_context.store_code})\n"
            f"Identity: {identifier}\n"
            f"Expiry: {expiry}"
        )
        self.home_store_summary_label.setText(
            f"{store_context.store_name} is the active store for this session. "
            f"{store_context.user_count} store user(s) are currently assigned to this location."
        )
        self.home_store_details_label.setText(
            f"Address: {location_line}\n"
            f"Contact: {store_context.contact_info}\n"
            f"Owner: {store_context.owner_name or 'Not set'}\n"
            f"Status: {store_context.status}"
        )
        self.home_session_label.setText(
            f"Current store: {store_context.store_name}\n"
            f"Store code: {store_context.store_code}\n"
            f"Current user: {identifier}\n"
            f"Session expiry: {expiry}"
        )
        self.sidebar_store_title.setText(store_context.store_name)
        self.sidebar_store_location_label.setText(location_line)
        self.sidebar_store_contact_label.setText(store_context.contact_info)

    def _refresh_home_route_content(self) -> None:
        is_superadmin = (
            self._current_user_id is not None
            and self._admin_user_management_service.role_name_for_user(self._current_user_id) == "Superadmin"
        )
        if is_superadmin:
            self.store_home_page.clear_context()
            self.home_mode_stack.setCurrentWidget(self.superadmin_home_page)
            return

        if self._is_store_admin_mode() and self._store_dashboard_context is not None:
            self.orders_management_page.clear_context()
            self.work_management_page.clear_context()
            if isinstance(self.billing_page, StorePaymentsScreen):
                if self._has_role("Accountant"):
                    self.billing_page.set_context(
                        current_user_id=self._current_user_id,
                        store_context=self._store_dashboard_context,
                    )
                else:
                    self.billing_page.clear_context()
            self.store_home_page.set_context(
                current_user_id=self._current_user_id,
                store_context=self._store_dashboard_context,
            )
            self.home_mode_stack.setCurrentWidget(self.store_home_page)
            return

        if self._is_store_manager_mode() and self._store_dashboard_context is not None:
            self.store_home_page.clear_context()
            self.store_manager_home_page.set_context(
                current_user_id=self._current_user_id,
                store_context=self._store_dashboard_context,
            )
            self.orders_management_page.set_context(
                current_user_id=self._current_user_id,
                store_context=self._store_dashboard_context,
            )
            self.work_management_page.set_context(
                current_user_id=self._current_user_id,
                store_context=self._store_dashboard_context,
            )
            if isinstance(self.billing_page, StorePaymentsScreen):
                if self._has_role("Accountant"):
                    self.billing_page.set_context(
                        current_user_id=self._current_user_id,
                        store_context=self._store_dashboard_context,
                    )
                else:
                    self.billing_page.clear_context()
            self.home_mode_stack.setCurrentWidget(self.store_manager_home_page)
            return

        if self._is_store_worker_mode() and self._store_dashboard_context is not None:
            self.store_home_page.clear_context()
            self.orders_management_page.clear_context()
            self.work_management_page.clear_context()
            if isinstance(self.billing_page, StorePaymentsScreen):
                self.billing_page.clear_context()
            self.home_mode_stack.setCurrentWidget(self.store_worker_home_page)
            return

        if self._has_role("Accountant") and self._store_dashboard_context is not None:
            self.store_home_page.clear_context()
            self.orders_management_page.clear_context()
            self.work_management_page.clear_context()
            if isinstance(self.billing_page, StorePaymentsScreen):
                self.billing_page.set_context(
                    current_user_id=self._current_user_id,
                    store_context=self._store_dashboard_context,
                )
            self.home_mode_stack.setCurrentWidget(self.default_home_page)
            return

        self.store_home_page.clear_context()
        self.orders_management_page.clear_context()
        self.work_management_page.clear_context()
        if isinstance(self.billing_page, StorePaymentsScreen):
            self.billing_page.clear_context()
        self.home_mode_stack.setCurrentWidget(self.default_home_page)

    def _refresh_store_admin_views(self) -> None:
        self.create_staff_page.set_current_user_id(self._current_user_id)
        self.create_items_page.set_current_user_id(self._current_user_id)
        if self._current_user_id is None or self._session_state is None:
            return
        self._refresh_store_admin_shell()
        self.admin_page.set_current_user_id(self._current_user_id)

    def _refresh_store_admin_shell(self) -> None:
        if self._current_user_id is None or self._session_state is None:
            return
        self._store_dashboard_context = self._admin_user_management_service.get_store_dashboard_context_for_user(
            self._current_user_id
        )
        expiry = self._session_state.expires_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self._refresh_store_scoped_shell(identifier=self._session_state.identifier, expiry=expiry)
        self._refresh_home_route_content()

    def _handle_store_staff_created(self) -> None:
        if self._current_user_id is None or self._session_state is None:
            return
        self._refresh_store_admin_shell()
        self.admin_page.set_current_user_id(self._current_user_id)

    def _handle_store_item_created(self) -> None:
        if self._current_user_id is None or self._session_state is None:
            return
        self._refresh_store_admin_shell()

    def _handle_manager_language_changed(self) -> None:
        if self._current_user_id is None or self._session_state is None:
            return
        self._refresh_store_admin_shell()
        self.store_manager_home_page.refresh_language()
        self.orders_management_page.refresh_language()
        self.work_management_page.refresh_language()

    def _update_workspace_chrome_visibility(self) -> None:
        store_scoped_mode = self._is_store_scoped_workspace_mode()
        store_dashboard_mode = store_scoped_mode and self._active_route == "home"
        full_content_mode = store_scoped_mode and self._active_route in {
            "orders_management",
            "work_management",
            "billing",
        }

        self.workspace_eyebrow.setVisible(not store_scoped_mode)
        self.sidebar_store_card.setVisible(not store_scoped_mode)
        self.page_eyebrow.setVisible(not store_dashboard_mode and not full_content_mode)
        self.page_title_label.setVisible(not store_dashboard_mode and not full_content_mode)
        self.page_subtitle_label.setVisible(
            (not store_dashboard_mode)
            and (not full_content_mode)
            and bool(self.page_subtitle_label.text())
        )
        self.workspace_notice.setVisible(
            (not store_dashboard_mode) and bool(self.workspace_notice.text())
        )

    def _is_store_admin_mode(self) -> bool:
        return (
            self._store_dashboard_context is not None
            and self._current_user_id is not None
            and self._admin_user_management_service.role_name_for_user(self._current_user_id) == "Admin"
        )

    def _is_store_manager_mode(self) -> bool:
        return (
            self._store_dashboard_context is not None
            and self._current_user_id is not None
            and self._admin_user_management_service.role_name_for_user(self._current_user_id) == "Manager"
        )

    def _is_store_worker_mode(self) -> bool:
        return (
            self._store_dashboard_context is not None
            and self._current_user_id is not None
            and self._admin_user_management_service.role_name_for_user(self._current_user_id) == "Worker"
        )

    def _has_role(self, role_name: str) -> bool:
        if self._current_user_id is None:
            return False
        profile = self._admin_user_management_service.get_user_profile(self._current_user_id)
        return profile is not None and role_name in profile.roles

    def _is_store_scoped_workspace_mode(self) -> bool:
        return (
            self._is_store_admin_mode()
            or self._is_store_manager_mode()
            or self._has_role("Accountant")
            or self._is_store_worker_mode()
        )

    def _log_context(self) -> dict[str, object]:
        return {
            "user_id": self._current_user_id or "",
            "route": self._active_route,
            "store_id": (
                self._store_dashboard_context.store_id
                if self._store_dashboard_context is not None
                else ""
            ),
        }

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
        log_ui_action("MainWindow", "open_forgot_password_page", **self._log_context())
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
        log_ui_action("MainWindow", "return_to_login_from_recovery", **self._log_context())
        identifier = self.recovery_identifier_input.text().strip()
        self._pending_password_reset = None
        self._set_status_label(self.recovery_status_label, "", tone="success")
        self._return_to_login(identifier=identifier)

    def _verify_password_recovery(self) -> None:
        log_ui_action("MainWindow", "verify_password_recovery", **self._log_context())
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
        log_ui_action("MainWindow", "cancel_password_reset", **self._log_context())
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
        log_ui_action("MainWindow", "return_to_login", **self._log_context())
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
            QFrame#MetricCard {
                background-color: #fcf9f5;
                border: 1px solid #ded2c3;
                border-radius: 14px;
            }
            QLabel#MetricValue {
                color: #111827;
                font-size: 16px;
                font-weight: 800;
            }
            QLabel#MetricTitle {
                color: #6b5b4a;
                font-size: 11px;
                font-weight: 700;
            }
            QFrame#DashboardListRow {
                background-color: #fcf9f5;
                border: 1px solid #ded2c3;
                border-radius: 14px;
            }
            QTableWidget#DashboardTable {
                background-color: #fcf9f5;
                alternate-background-color: #f8f2eb;
                border: 1px solid #ded2c3;
                border-radius: 14px;
                color: #1f2933;
                gridline-color: #eadfd2;
                outline: none;
            }
            QTableWidget#DashboardTable::item {
                padding: 8px 12px;
                border-bottom: 1px solid #eadfd2;
            }
            QTableWidget#DashboardTable::item:selected {
                background-color: #ddebe8;
                color: #1f2933;
            }
            QTableWidget#DashboardTable QHeaderView::section {
                background-color: #e8ddd0;
                color: #3d3025;
                border: none;
                border-bottom: 1px solid #d6c6b5;
                padding: 10px 12px;
                font-size: 12px;
                font-weight: 700;
                text-align: left;
            }
            QTableWidget#DashboardTable QTableCornerButton::section {
                background-color: #e8ddd0;
                border: none;
                border-bottom: 1px solid #d6c6b5;
            }
            QTableWidget#PaymentsFlatTable {
                background-color: transparent;
                alternate-background-color: #f8f2eb;
                border: none;
                border-radius: 0px;
                color: #1f2933;
                gridline-color: #eadfd2;
                outline: none;
            }
            QTableWidget#PaymentsFlatTable::viewport {
                background-color: transparent;
                border: none;
            }
            QTableWidget#PaymentsFlatTable::item {
                padding: 8px 12px;
                border-bottom: 1px solid #eadfd2;
            }
            QTableWidget#PaymentsFlatTable::item:selected {
                background-color: #ddebe8;
                color: #1f2933;
            }
            QTableWidget#PaymentsFlatTable QHeaderView::section {
                background-color: #e8ddd0;
                color: #3d3025;
                border: none;
                border-bottom: 1px solid #d6c6b5;
                padding: 10px 12px;
                font-size: 12px;
                font-weight: 700;
                text-align: left;
            }
            QTableWidget#PaymentsFlatTable QTableCornerButton::section {
                background-color: #e8ddd0;
                border: none;
                border-bottom: 1px solid #d6c6b5;
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
            QLabel#DashboardRowPrimary {
                font-size: 14px;
                font-weight: 700;
                color: #1f2933;
            }
            QLabel#DashboardRowSecondary {
                font-size: 12px;
                color: #52606d;
            }
            QLabel#DashboardPlaceholder {
                font-size: 14px;
                color: #52606d;
            }
            QLabel#PageTitle {
                font-size: 28px;
            }
            QLabel#PageEyebrow, QLabel#SidebarHeading {
                font-size: 11px;
                font-weight: 700;
                color: #8b5a2b;
            }
            QLabel#FooterLabel {
                background-color: #e7ddd1;
                border-top: 1px solid #d2c1ad;
                color: #5c5349;
                font-size: 12px;
                font-weight: 600;
                padding: 10px 18px;
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
            QComboBox, QDateEdit {
                min-height: 42px;
                padding: 0 12px;
                border: 1px solid #cbb9a3;
                border-radius: 12px;
                background-color: #ffffff;
                color: #1f2933;
            }
            QComboBox:focus, QDateEdit:focus {
                border: 1px solid #8b5a2b;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1f2933;
                selection-background-color: #ddebe8;
                selection-color: #1f2933;
            }
            QLabel#WorkerPaymentCompactLabel {
                color: #3d3025;
                font-size: 8pt;
                font-weight: 700;
                padding: 0;
                margin: 0;
            }
            QLineEdit#WorkerPaymentCompactInput,
            QComboBox#WorkerPaymentCompactInput {
                min-height: 34px;
                max-height: 34px;
                padding: 0;
                margin: 0;
                border: 1px solid #cbb9a3;
                border-radius: 10px;
                background-color: #ffffff;
                color: #1f2933;
                font-size: 8pt;
            }
            QComboBox#WorkerPaymentCompactInput::drop-down {
                width: 20px;
                border: none;
                padding: 0;
                margin: 0;
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
