from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timezone
from typing import Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.admin.services import AdminUserManagementService
from app.platform.audit import AuditActor, AuditEventType, AuditQuery, AuditReviewService, AuditService
from app.platform.logging.context import ensure_correlation_id


@dataclass(slots=True)
class RoleRecord:
    role_key: str
    role_name: str
    scope: str
    assignments: int


@dataclass(slots=True)
class PermissionRecord:
    permission_key: str
    module: str
    action: str
    risk_level: str


class _AdminTableModel(QAbstractTableModel):
    def __init__(self, headers: list[str], rows: list[tuple[str, ...]], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._headers = headers
        self._rows = rows

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        value = row[index.column()]

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return value

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            return self._headers[section]

        return str(section + 1)

    def replace_rows(self, rows: list[tuple[str, ...]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_values(self, row_index: int) -> tuple[str, ...] | None:
        if row_index < 0 or row_index >= len(self._rows):
            return None
        return self._rows[row_index]


class AdminFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._exact_filter_column = -1
        self._exact_filter_value = "All"
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)

    def set_exact_filter(self, column: int, value: str) -> None:
        self._exact_filter_column = column
        self._exact_filter_value = value
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        base_match = super().filterAcceptsRow(source_row, source_parent)
        if not base_match:
            return False

        if self._exact_filter_column < 0 or self._exact_filter_value == "All":
            return True

        index = self.sourceModel().index(source_row, self._exact_filter_column, source_parent)
        source_value = self.sourceModel().data(index, Qt.ItemDataRole.DisplayRole)
        return str(source_value) == self._exact_filter_value


class ManagementGridScreen(QWidget):
    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        headers: list[str],
        rows: list[tuple[str, ...]],
        filter_label: str,
        filter_column: int,
        filter_options: list[str],
        search_placeholder: str = "Type to search all columns...",
        show_header: bool = True,
        show_status: bool = True,
        show_search: bool = True,
        compact_controls: bool = False,
        sync_filter_options_from_rows: bool = False,
        default_sort_column: int = 0,
        default_sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._filter_column = filter_column
        self._show_status = show_status
        self._sync_filter_options_from_rows = sync_filter_options_from_rows
        self._default_sort_column = default_sort_column
        self._default_sort_order = default_sort_order

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        subheading = QLabel(subtitle)
        subheading.setStyleSheet("color: #555;")
        subheading.setWordWrap(True)

        controls = QHBoxLayout()
        controls.setContentsMargins(4, 0, 4, 0)
        controls.setSpacing(10)
        has_controls = False
        control_label_style = "font-size: 13px; font-weight: 600; color: #5e584f;"
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(search_placeholder)
        self.search_input.setMinimumWidth(260)
        self.search_input.setClearButtonEnabled(True)

        self.filter_combo = QComboBox()
        initial_filter_options = (
            self._filter_values_for_rows(rows)
            if self._sync_filter_options_from_rows
            else filter_options
        )
        self.filter_combo.addItems(["All", *initial_filter_options])
        self.filter_combo.setMinimumWidth(140)
        self.filter_combo.setMinimumHeight(42)
        self.filter_combo.setStyleSheet(
            "QComboBox { background-color: white; color: #1f2933; border: 1px solid #d7c9b8; "
            "border-radius: 10px; padding: 8px 10px; } "
            "QComboBox QAbstractItemView { background-color: white; color: #1f2933; "
            "selection-background-color: #dbe8df; selection-color: #1f2933; }"
        )

        if show_search:
            self.search_label = QLabel("Search")
            self.search_label.setStyleSheet(control_label_style)
            if compact_controls:
                controls.addWidget(self.search_input, stretch=1)
            else:
                controls.addWidget(self.search_label)
                controls.addWidget(self.search_input, stretch=2)
            has_controls = True
        else:
            self.search_label = QLabel("Search")
            self.search_label.hide()
            self.search_input.hide()

        self.filter_label_widget = QLabel(filter_label)
        self.filter_label_widget.setStyleSheet(control_label_style)
        if compact_controls:
            controls.addWidget(self.filter_label_widget)
            controls.addWidget(self.filter_combo)
        else:
            controls.addWidget(self.filter_label_widget)
            controls.addWidget(self.filter_combo)
        has_controls = True

        controls.addStretch(1)

        self.model = _AdminTableModel(headers=headers, rows=rows, parent=self)
        self.proxy_model = AdminFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(self._default_sort_column, self._default_sort_order)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(
            "QTableView { background-color: #fffdfa; color: #1f2933; border: 1px solid #d7c9b8; "
            "border-radius: 14px; alternate-background-color: #f8f1e8; selection-background-color: #dbe8df; "
            "selection-color: #1f2933; gridline-color: #eadfce; } "
            "QTableView::item { padding: 8px 10px; border-bottom: 1px solid #efe5d9; } "
            "QTableView::item:selected { background-color: #dbe8df; color: #1f2933; } "
            "QTableView::item:selected:active { background-color: #dbe8df; color: #1f2933; } "
            "QTableView::item:selected:!active { background-color: #e8efe9; color: #1f2933; } "
            "QHeaderView::section { background-color: #f3eadf; color: #1f2933; border: none; "
            "border-bottom: 1px solid #d7c9b8; padding: 10px 12px; font-weight: 600; }"
        )

        self.status_label = QLabel(self._status_text())
        self.status_label.setStyleSheet("color: #555;")

        if show_header:
            root.addWidget(heading)
            root.addWidget(subheading)
        if has_controls:
            root.addLayout(controls)
        root.addWidget(self.table, stretch=1)
        if show_status:
            root.addWidget(self.status_label)
        else:
            self.status_label.hide()

        self.search_input.textChanged.connect(self._on_search_changed)
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        self.table.clicked.connect(self._select_row_from_index)
        self.proxy_model.rowsInserted.connect(lambda *_: self._refresh_status())
        self.proxy_model.rowsRemoved.connect(lambda *_: self._refresh_status())
        self.proxy_model.modelReset.connect(self._refresh_status)

    def _status_text(self) -> str:
        return f"Showing {self.proxy_model.rowCount()} of {self.model.rowCount()} records"

    def _refresh_status(self) -> None:
        if not self._show_status:
            return
        self.status_label.setText(self._status_text())

    def _on_search_changed(self, text: str) -> None:
        self.proxy_model.setFilterFixedString(text)
        self._refresh_status()

    def _on_filter_changed(self, value: str) -> None:
        self.proxy_model.set_exact_filter(column=self._filter_column, value=value)
        self._refresh_status()

    def update_rows(self, rows: list[tuple[str, ...]]) -> None:
        current_filter_value = self.filter_combo.currentText()
        self.model.replace_rows(rows)
        if self._sync_filter_options_from_rows:
            self._sync_filter_options(rows=rows, selected_value=current_filter_value)
        self.table.sortByColumn(self._default_sort_column, self._default_sort_order)
        self._refresh_status()

    def row_values_for_index(self, index: QModelIndex) -> tuple[str, ...] | None:
        if not index.isValid():
            return None
        source_index = self.proxy_model.mapToSource(index)
        return self.model.row_values(source_index.row())

    def selected_row_values(self) -> tuple[str, ...] | None:
        return self.row_values_for_index(self.table.currentIndex())

    def _select_row_from_index(self, index: QModelIndex) -> None:
        if index.isValid():
            self.table.selectRow(index.row())

    def _filter_values_for_rows(self, rows: list[tuple[str, ...]]) -> list[str]:
        values = {
            str(row[self._filter_column]).strip()
            for row in rows
            if self._filter_column >= 0 and len(row) > self._filter_column and str(row[self._filter_column]).strip()
        }
        return sorted(values, key=str.casefold)

    def _sync_filter_options(self, *, rows: list[tuple[str, ...]], selected_value: str) -> None:
        available_values = self._filter_values_for_rows(rows)
        resolved_value = selected_value if selected_value in available_values else "All"
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItems(["All", *available_values])
        self.filter_combo.setCurrentText(resolved_value)
        self.filter_combo.blockSignals(False)
        self.proxy_model.set_exact_filter(column=self._filter_column, value=resolved_value)


class AuditReviewScreen(QWidget):
    def __init__(self, review_service: AuditReviewService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._review_service = review_service

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        heading = QLabel("Audit Review")
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        subheading = QLabel(
            "Investigate login, admin, and permission events with focused filters."
        )
        subheading.setStyleSheet("color: #555;")

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Event Type"))
        self.event_type_combo = QComboBox()
        self.event_type_combo.addItems(["All", *[event_type.value for event_type in AuditEventType]])
        controls.addWidget(self.event_type_combo)

        controls.addWidget(QLabel("Actor"))
        self.actor_input = QLineEdit()
        self.actor_input.setPlaceholderText("user id (optional)")
        controls.addWidget(self.actor_input)

        controls.addWidget(QLabel("Correlation ID"))
        self.correlation_input = QLineEdit()
        self.correlation_input.setPlaceholderText("trace a full workflow")
        controls.addWidget(self.correlation_input)

        self.refresh_button = QPushButton("Run Query")
        controls.addWidget(self.refresh_button)

        self.model = _AdminTableModel(
            headers=["Occurred", "Type", "Actor", "Correlation", "Payload Summary"],
            rows=[],
            parent=self,
        )
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.strategy_label = QLabel(
            "Query strategy: start with event type, then narrow by actor or correlation ID."
        )
        self.strategy_label.setWordWrap(True)
        self.strategy_label.setStyleSheet("color: #555;")

        root.addWidget(heading)
        root.addWidget(subheading)
        root.addLayout(controls)
        root.addWidget(self.table)
        root.addWidget(self.strategy_label)

        self.refresh_button.clicked.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        selected = self.event_type_combo.currentText()
        event_type = None if selected == "All" else AuditEventType(selected)
        actor_id = self.actor_input.text().strip() or None
        correlation_id = self.correlation_input.text().strip() or None
        rows = self._review_service.query(
            AuditQuery(
                event_type=event_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                limit=200,
            )
        )
        self.model = _AdminTableModel(
            headers=["Occurred", "Type", "Actor", "Correlation", "Payload Summary"],
            rows=[
                (row.occurred_at, row.event_type, row.actor_id, row.correlation_id, row.summary)
                for row in rows
            ],
            parent=self,
        )
        self.table.setModel(self.model)


class ManageUsersScreen(QWidget):
    def __init__(
        self,
        *,
        current_user_id: str | None,
        user_management_service: AdminUserManagementService,
        on_admin_change: Callable[[str, str], None] | None = None,
        on_permission_change: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._current_user_id = current_user_id
        self._user_management_service = user_management_service
        self._on_admin_change = on_admin_change
        self._on_permission_change = on_permission_change
        self._apply_styles()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QFrame.Shape.NoFrame)

        page_content = QWidget()
        page_layout = QVBoxLayout(page_content)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(16)

        intro_panel = QWidget()
        intro_layout = QVBoxLayout(intro_panel)
        intro_layout.setContentsMargins(0, 0, 0, 0)
        intro_layout.setSpacing(10)

        intro_heading = QLabel("Manage User Profile")
        intro_heading.setObjectName("ManagePageTitle")
        self.intro_copy = QLabel("")
        self.intro_copy.setObjectName("ManageMutedText")
        self.intro_copy.setWordWrap(True)
        self.scope_label = QLabel("")
        self.scope_label.setObjectName("ManageFeedback")
        self.scope_label.setWordWrap(True)

        selector_row = QHBoxLayout()
        selector_label = QLabel("User name")
        selector_label.setObjectName("ManageFormLabel")
        selector_row.addWidget(selector_label)
        self.user_selector = QComboBox()
        self.user_selector.setMinimumWidth(320)
        selector_row.addWidget(self.user_selector)
        self.add_user_button = QPushButton("Add New User")
        self.add_user_button.setObjectName("ManageSecondaryButton")
        selector_row.addWidget(self.add_user_button)
        selector_row.addStretch(1)

        intro_layout.addWidget(intro_heading)
        intro_layout.addWidget(self.intro_copy)
        intro_layout.addWidget(self.scope_label)
        intro_layout.addLayout(selector_row)

        password_panel = QWidget()
        password_panel_layout = QHBoxLayout(password_panel)
        password_panel_layout.setContentsMargins(0, 0, 0, 0)
        password_panel_layout.setSpacing(10)
        self.temporary_password_label = QLabel("")
        self.temporary_password_label.setObjectName("ManageTemporaryPassword")
        self.copy_password_button = QPushButton("Copy Password")
        self.copy_password_button.setObjectName("ManageSecondaryButton")
        self.hide_password_button = QPushButton("Hide")
        self.hide_password_button.setObjectName("ManageSecondaryButton")
        password_panel_layout.addWidget(self.temporary_password_label, stretch=1)
        password_panel_layout.addWidget(self.copy_password_button)
        password_panel_layout.addWidget(self.hide_password_button)
        self.temporary_password_panel = password_panel
        self.temporary_password_panel.hide()

        intro_layout.addWidget(self.temporary_password_panel)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(18)

        profile_panel = QWidget()
        profile_layout = QVBoxLayout(profile_panel)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(12)

        details_heading = QLabel("Profile And Access")
        details_heading.setObjectName("ManageSectionTitle")
        details_copy = QLabel(
            "Editable fields: name, contact information, roles, and permissions. Username is editable only while creating a new user, and created-on remains read-only."
        )
        details_copy.setObjectName("ManageMutedText")
        details_copy.setWordWrap(True)

        details_form = QFormLayout()
        details_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        details_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        details_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        details_form.setHorizontalSpacing(14)
        details_form.setVerticalSpacing(14)

        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Enter full name")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter a unique username")
        self.contact_info_input = QLineEdit()
        self.contact_info_input.setPlaceholderText("Enter phone number and email")
        self.created_on_input = self._build_readonly_input()
        self._set_username_editable(False)

        details_form.addRow(self._form_label("Name"), self.full_name_input)
        details_form.addRow(self._form_label("Username"), self.username_input)
        details_form.addRow(self._form_label("Contact information"), self.contact_info_input)
        details_form.addRow(self._form_label("Created on"), self.created_on_input)

        roles_panel = QWidget()
        roles_panel_layout = QVBoxLayout(roles_panel)
        roles_panel_layout.setContentsMargins(0, 0, 0, 0)
        roles_panel_layout.setSpacing(6)
        roles_copy = QLabel("Select one or more roles.")
        roles_copy.setObjectName("ManageMutedText")
        roles_copy.setWordWrap(True)
        self.roles_list = QListWidget()
        self.roles_list.setAlternatingRowColors(True)
        self.roles_list.setMinimumHeight(180)
        self._populate_checkable_list(
            self.roles_list,
            list(self._user_management_service.role_options()),
        )
        roles_panel_layout.addWidget(roles_copy)
        roles_panel_layout.addWidget(self.roles_list)

        permissions_panel = QWidget()
        permissions_panel_layout = QVBoxLayout(permissions_panel)
        permissions_panel_layout.setContentsMargins(0, 0, 0, 0)
        permissions_panel_layout.setSpacing(6)
        permissions_copy = QLabel("Select one or more permissions.")
        permissions_copy.setObjectName("ManageMutedText")
        permissions_copy.setWordWrap(True)
        self.permissions_list = QListWidget()
        self.permissions_list.setAlternatingRowColors(True)
        self.permissions_list.setMinimumHeight(180)
        self._populate_checkable_list(
            self.permissions_list,
            list(self._user_management_service.permission_options()),
        )
        permissions_panel_layout.addWidget(permissions_copy)
        permissions_panel_layout.addWidget(self.permissions_list)

        details_form.addRow(self._form_label("Roles"), roles_panel)
        details_form.addRow(self._form_label("Permissions"), permissions_panel)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_changes_button = QPushButton("Cancel")
        self.cancel_changes_button.setObjectName("ManageSecondaryButton")
        self.save_changes_button = QPushButton("Save User Details")
        actions.addWidget(self.cancel_changes_button)
        actions.addWidget(self.save_changes_button)

        self.feedback_label = QLabel(
            "Select a user to load profile details and activity history."
        )
        self.feedback_label.setObjectName("ManageFeedback")
        self.feedback_label.setWordWrap(True)

        profile_layout.addWidget(details_heading)
        profile_layout.addWidget(details_copy)
        profile_layout.addLayout(details_form)
        profile_layout.addWidget(self.feedback_label)
        profile_layout.addLayout(actions)
        profile_layout.addStretch(1)

        activity_panel = QWidget()
        activity_layout = QVBoxLayout(activity_panel)
        activity_layout.setContentsMargins(0, 0, 0, 0)
        activity_layout.setSpacing(12)

        activity_heading = QLabel("Activity History")
        activity_heading.setObjectName("ManageSectionTitle")
        activity_copy = QLabel(
            "Recent activity is listed in descending order, with the newest event at the top."
        )
        activity_copy.setObjectName("ManageMutedText")
        activity_copy.setWordWrap(True)

        self.activity_model = _AdminTableModel(
            headers=["Occurred", "Activity"],
            rows=[],
            parent=self,
        )
        self.activity_table = QTableView()
        self.activity_table.setModel(self.activity_model)
        self.activity_table.setSortingEnabled(False)
        self.activity_table.setAlternatingRowColors(True)
        self.activity_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.horizontalHeader().setStretchLastSection(True)
        self.activity_table.setMinimumHeight(440)

        self.activity_summary_label = QLabel("")
        self.activity_summary_label.setObjectName("ManageMutedText")
        self.activity_summary_label.setWordWrap(True)

        activity_layout.addWidget(activity_heading)
        activity_layout.addWidget(activity_copy)
        activity_layout.addWidget(self.activity_table, stretch=1)
        activity_layout.addWidget(self.activity_summary_label)
        activity_layout.addStretch(1)

        content_row.addWidget(profile_panel, 5)
        content_row.addWidget(activity_panel, 4)

        page_layout.addWidget(intro_panel)
        page_layout.addLayout(content_row)
        page_layout.addStretch(1)
        page_scroll.setWidget(page_content)
        root.addWidget(page_scroll)

        self._is_creating_user = False
        self._temporary_password_value = ""
        self.refresh_reference_data()
        self._populate_user_selector()
        self.user_selector.currentIndexChanged.connect(self._on_user_selection_changed)
        self.add_user_button.clicked.connect(self._start_new_user)
        self.cancel_changes_button.clicked.connect(self._cancel_changes)
        self.save_changes_button.clicked.connect(self._save_changes)
        self.copy_password_button.clicked.connect(self._copy_temporary_password)
        self.hide_password_button.clicked.connect(self._hide_temporary_password)
        self._load_selected_user()

    def _build_readonly_input(self) -> QLineEdit:
        widget = QLineEdit()
        widget.setReadOnly(True)
        return widget

    def _form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("ManageFormLabel")
        label.setWordWrap(True)
        return label

    def _set_username_editable(self, editable: bool) -> None:
        self.username_input.setReadOnly(not editable)
        self.username_input.setClearButtonEnabled(editable)

    def _set_manage_mode(self, *, creating_user: bool) -> None:
        self._is_creating_user = creating_user
        self._set_username_editable(creating_user)
        self.save_changes_button.setText("Create User" if creating_user else "Save User Details")

    def _populate_user_selector(self, selected_user_id: str | None = None) -> None:
        users = self._user_management_service.list_users(actor_user_id=self._current_user_id)
        self.user_selector.blockSignals(True)
        self.user_selector.clear()
        selected_index = 0
        for index, user in enumerate(users):
            self.user_selector.addItem(user.full_name, user.user_id)
            if selected_user_id is not None and user.user_id == selected_user_id:
                selected_index = index
        if users:
            self.user_selector.setCurrentIndex(selected_index)
        self.user_selector.blockSignals(False)

    def _on_user_selection_changed(self) -> None:
        self._hide_temporary_password()
        self._set_manage_mode(creating_user=False)
        self._load_selected_user()

    def _populate_checkable_list(self, widget: QListWidget, options: list[str]) -> None:
        widget.clear()
        for option in options:
            item = QListWidgetItem(option)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            widget.addItem(item)

    def refresh_reference_data(self) -> None:
        selected_roles = self._checked_values(self.roles_list)
        selected_permissions = self._checked_values(self.permissions_list)
        available_roles = self._user_management_service.available_roles_for_actor(
            self._current_user_id
        )
        self._populate_checkable_list(
            self.roles_list,
            list(available_roles),
        )
        self._populate_checkable_list(
            self.permissions_list,
            list(self._user_management_service.permission_options()),
        )
        self._set_checked_items(self.roles_list, selected_roles)
        self._set_checked_items(self.permissions_list, selected_permissions)
        self.add_user_button.setVisible(
            self._user_management_service.can_actor_create_users(self._current_user_id)
        )
        self._refresh_scope_copy()

    def set_current_user_id(self, current_user_id: str | None) -> None:
        self._current_user_id = current_user_id
        self._hide_temporary_password()
        self._set_manage_mode(creating_user=False)
        self.refresh_reference_data()
        self._populate_user_selector()
        self._load_selected_user()

    def _selected_user_id(self) -> str | None:
        user_id = self.user_selector.currentData()
        if user_id is None:
            return None
        return str(user_id)

    def _start_new_user(self) -> None:
        self._hide_temporary_password()
        self._set_manage_mode(creating_user=True)
        self.full_name_input.clear()
        self.username_input.clear()
        self.contact_info_input.clear()
        self.created_on_input.setText("Set automatically when the user is created")
        self._set_checked_items(self.roles_list, [])
        self._set_checked_items(self.permissions_list, [])
        self._set_activity_rows(
            rows=[("-", "Activity history will appear after the new user is created.")],
            summary="New users will show their creation event and later activity after save.",
        )
        self.feedback_label.setText(
            "Enter name, username, contact information, and optional access assignments, then create the new user."
        )
        self.full_name_input.setFocus()

    def _load_selected_user(self) -> None:
        user_id = self._selected_user_id()
        if user_id is None:
            self.full_name_input.clear()
            self.username_input.clear()
            self.contact_info_input.clear()
            self.created_on_input.clear()
            self._set_checked_items(self.roles_list, [])
            self._set_checked_items(self.permissions_list, [])
            self._set_activity_rows(
                rows=[("-", "No store-scoped users are currently available.")],
                summary="Create a new store user to populate this workspace.",
            )
            self.feedback_label.setText(
                "No users are available in the current store scope yet."
            )
            return

        profile = self._user_management_service.get_user_profile(user_id)
        if profile is None:
            return

        self._set_manage_mode(creating_user=False)
        self.full_name_input.setText(profile.full_name)
        self.username_input.setText(profile.username)
        self.contact_info_input.setText(profile.contact_info)
        self.created_on_input.setText(profile.created_on.strftime("%Y-%m-%d %H:%M UTC"))
        self._set_checked_items(self.roles_list, list(profile.roles))
        self._set_checked_items(self.permissions_list, list(profile.permissions))
        self._refresh_activity(profile.user_id)
        self.feedback_label.setText(
            f"Loaded {profile.full_name}. Edit the allowed fields, then save."
        )

    def _show_temporary_password(self, *, username: str, temporary_password: str) -> None:
        self._temporary_password_value = temporary_password
        self.temporary_password_label.setText(
            f"Temporary password for {username}: {temporary_password}"
        )
        self.temporary_password_panel.show()

    def _hide_temporary_password(self) -> None:
        self._temporary_password_value = ""
        self.temporary_password_label.setText("")
        self.temporary_password_panel.hide()

    def _copy_temporary_password(self) -> None:
        if not self._temporary_password_value:
            return
        QApplication.clipboard().setText(self._temporary_password_value)
        self.feedback_label.setText("Temporary password copied to the clipboard.")

    def _set_checked_items(self, widget: QListWidget, selected_values: list[str]) -> None:
        selected_set = set(selected_values)
        for index in range(widget.count()):
            item = widget.item(index)
            item.setCheckState(
                Qt.CheckState.Checked if item.text() in selected_set else Qt.CheckState.Unchecked
            )

    def _checked_values(self, widget: QListWidget) -> list[str]:
        values: list[str] = []
        for index in range(widget.count()):
            item = widget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                values.append(item.text())
        return values

    def _set_activity_rows(self, *, rows: list[tuple[str, str]], summary: str) -> None:
        self.activity_model = _AdminTableModel(
            headers=["Occurred", "Activity"],
            rows=rows,
            parent=self,
        )
        self.activity_table.setModel(self.activity_model)
        self.activity_summary_label.setText(summary)

    def _refresh_activity(self, user_id: str) -> None:
        profile = self._user_management_service.get_user_profile(user_id)
        if profile is None:
            return

        rows = [
            (
                activity.occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                activity.summary,
            )
            for activity in profile.activities
        ]
        if not rows:
            rows = [("-", "No recorded activity.")]

        self._set_activity_rows(
            rows=rows,
            summary=(
                f"Showing {len(profile.activities)} activity item(s) for {profile.full_name}, newest first."
            ),
        )

    def _cancel_changes(self) -> None:
        if self._is_creating_user:
            self._set_manage_mode(creating_user=False)
            self._hide_temporary_password()
            self._load_selected_user()
            if self.user_selector.currentText():
                self.feedback_label.setText(
                    f"Canceled new user creation. Restored {self.user_selector.currentText()}."
                )
            return

        user_id = self._selected_user_id()
        if user_id is None:
            return

        self._load_selected_user()
        profile = self._user_management_service.get_user_profile(user_id)
        if profile is None:
            return
        self.feedback_label.setText(
            f"Reverted unsaved changes for {profile.full_name}."
        )

    def _save_changes(self) -> None:
        if self._is_creating_user:
            self._create_user()
            return

        user_id = self._selected_user_id()
        if user_id is None:
            return

        profile = self._user_management_service.get_user_profile(user_id)
        if profile is None:
            return

        full_name = self.full_name_input.text().strip()
        contact_info = self.contact_info_input.text().strip()
        selected_roles = sorted(self._checked_values(self.roles_list))
        selected_permissions = sorted(self._checked_values(self.permissions_list))
        current_roles = sorted(profile.roles)
        current_permissions = sorted(profile.permissions)

        if not full_name or not contact_info:
            self.feedback_label.setText(
                "Name and contact information are required before the record can be saved."
            )
            return

        change_notes: list[str] = []
        if profile.full_name != full_name:
            change_notes.append("name updated")
        if profile.contact_info != contact_info:
            change_notes.append("contact information updated")
        if current_roles != selected_roles:
            change_notes.append("roles updated")
        if current_permissions != selected_permissions:
            change_notes.append("permissions updated")

        if not change_notes:
            self.feedback_label.setText(
                f"No changes detected for {profile.full_name}. The form already matches the saved record."
            )
            return

        try:
            self._user_management_service.save_user_profile(
                actor_user_id=self._current_user_id,
                user_id=user_id,
                full_name=full_name,
                contact_info=contact_info,
                roles=selected_roles,
                permissions=selected_permissions,
            )
        except ValueError as exc:
            self.feedback_label.setText(str(exc))
            return

        if (profile.full_name != full_name or profile.contact_info != contact_info) and self._on_admin_change is not None:
            self._on_admin_change("update_user_profile", f"{user_id}:{full_name}:{contact_info}")
        if current_roles != selected_roles and self._on_admin_change is not None:
            self._on_admin_change(
                "update_user_roles",
                f"{user_id}:{', '.join(selected_roles) or 'none'}",
            )
        if current_permissions != selected_permissions and self._on_permission_change is not None:
            self._on_permission_change(
                "update_user_permissions",
                f"{user_id}:{', '.join(selected_permissions) or 'none'}",
            )

        self._populate_user_selector(selected_user_id=user_id)
        self._load_selected_user()
        self.feedback_label.setText(f"Saved {', '.join(change_notes)} for {full_name}.")

    def _create_user(self) -> None:
        full_name = self.full_name_input.text().strip()
        username = self.username_input.text().strip()
        contact_info = self.contact_info_input.text().strip()
        selected_roles = sorted(self._checked_values(self.roles_list))
        selected_permissions = sorted(self._checked_values(self.permissions_list))

        if not full_name or not username or not contact_info:
            self.feedback_label.setText(
                "Name, username, and contact information are required before a new user can be created."
            )
            return

        if not re.fullmatch(r"[a-zA-Z0-9._-]+", username):
            self.feedback_label.setText(
                "Username can only contain letters, numbers, dots, underscores, and hyphens."
            )
            return

        temporary_password = self._user_management_service.default_password_for_username(username)
        try:
            user_id = self._user_management_service.create_user(
                actor_user_id=self._current_user_id,
                username=username,
                full_name=full_name,
                contact_info=contact_info,
                temporary_password=temporary_password,
                roles=selected_roles,
                permissions=selected_permissions,
            )
        except ValueError as exc:
            self.feedback_label.setText(str(exc))
            return

        normalized_username = username.lower()
        if self._on_admin_change is not None:
            self._on_admin_change("create_user", f"{user_id}:{normalized_username}:{full_name}")
            if selected_roles:
                self._on_admin_change(
                    "create_user_roles",
                    f"{user_id}:{', '.join(selected_roles)}",
                )
        if selected_permissions and self._on_permission_change is not None:
            self._on_permission_change(
                "create_user_permissions",
                f"{user_id}:{', '.join(selected_permissions)}",
            )

        self._populate_user_selector(selected_user_id=user_id)
        self._load_selected_user()
        self._show_temporary_password(
            username=normalized_username,
            temporary_password=temporary_password,
        )
        self.feedback_label.setText(
            f"Created {full_name} with username {normalized_username}. Share the temporary password now because it is only shown at creation time."
        )

    def _refresh_scope_copy(self) -> None:
        store_context = self._user_management_service.get_store_dashboard_context_for_user(
            self._current_user_id
        )
        if store_context is None:
            self.intro_copy.setText(
                "Choose an existing user by name or start a new user record, then review access assignments and inspect the latest activity first."
            )
            self.scope_label.hide()
            return

        self.intro_copy.setText(
            "This workspace is scoped to the signed-in store. Only users created for this store appear here, and any new users created here will belong to the same store."
        )
        location_line = store_context.address or store_context.city
        self.scope_label.setText(
            f"{store_context.store_name} | {location_line} | {store_context.contact_info}"
        )
        self.scope_label.show()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QLabel {
                color: #2f241b;
            }
            QLabel#ManagePageTitle {
                font-size: 22px;
                font-weight: 700;
                color: #1f2933;
            }
            QLabel#ManageSectionTitle {
                font-size: 18px;
                font-weight: 700;
                color: #1f2933;
            }
            QLabel#ManageFormLabel {
                font-size: 13px;
                font-weight: 700;
                color: #3d3025;
            }
            QLabel#ManageMutedText {
                font-size: 13px;
                color: #5e584f;
            }
            QLabel#ManageFeedback {
                background-color: #fffaeb;
                color: #8b5a2b;
                border: 1px solid #e6d7c5;
                border-radius: 10px;
                padding: 8px 10px;
                font-weight: 600;
            }
            QLabel#ManageTemporaryPassword {
                background-color: #eef7f2;
                color: #125d3f;
                border: 1px solid #c9e7d1;
                border-radius: 10px;
                padding: 10px 12px;
                font-weight: 700;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QComboBox,
            QLineEdit,
            QListWidget,
            QTableView {
                color: #1f2933;
                background-color: #fffdf9;
                border: 1px solid #d4c6b8;
                border-radius: 10px;
                selection-background-color: #dbe8df;
                selection-color: #1f2933;
            }
            QComboBox,
            QLineEdit {
                min-height: 40px;
                padding: 0 12px;
            }
            QComboBox {
                padding-right: 28px;
            }
            QComboBox QAbstractItemView {
                color: #1f2933;
                background-color: #fffdf9;
                border: 1px solid #d4c6b8;
                selection-background-color: #dbe8df;
                selection-color: #1f2933;
            }
            QLineEdit[readOnly="true"] {
                background-color: #f1e7dc;
                color: #43392f;
            }
            QListWidget {
                padding: 6px;
            }
            QListWidget::item {
                color: #1f2933;
                padding: 4px 6px;
            }
            QListWidget::item:selected {
                background-color: #dbe8df;
                color: #1f2933;
            }
            QTableView {
                alternate-background-color: #f7f1ea;
                gridline-color: #eadfce;
            }
            QTableView::item {
                color: #1f2933;
                padding: 6px 8px;
            }
            QHeaderView::section {
                background-color: #efe5d9;
                color: #3d3025;
                border: none;
                border-bottom: 1px solid #d4c6b8;
                padding: 8px 10px;
                font-weight: 700;
            }
            QPushButton#ManageSecondaryButton {
                background-color: #efe5d9;
                color: #1f2933;
                border: 1px solid #d7c9b8;
            }
            QPushButton#ManageSecondaryButton:hover {
                background-color: #e6d7c5;
            }
            """
        )


class AdminSettingsScreen(QWidget):
    def __init__(
        self,
        *,
        on_admin_change: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_admin_change = on_admin_change

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        heading = QLabel("Admin Settings")
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        copy = QLabel(
            "Adjust common access-control settings without leaving the admin console."
        )
        copy.setWordWrap(True)
        copy.setStyleSheet("color: #555;")

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.session_timeout_combo = QComboBox()
        self.session_timeout_combo.addItems(["15 minutes", "30 minutes", "60 minutes"])
        self.session_timeout_combo.setCurrentText("30 minutes")

        self.password_rotation_combo = QComboBox()
        self.password_rotation_combo.addItems(["30 days", "60 days", "90 days"])
        self.password_rotation_combo.setCurrentText("60 days")

        self.lockout_combo = QComboBox()
        self.lockout_combo.addItems(["3 attempts", "5 attempts", "7 attempts"])
        self.lockout_combo.setCurrentText("5 attempts")

        self.audit_retention_combo = QComboBox()
        self.audit_retention_combo.addItems(["90 days", "180 days", "365 days"])
        self.audit_retention_combo.setCurrentText("180 days")

        form.addRow("Session timeout", self.session_timeout_combo)
        form.addRow("Password rotation", self.password_rotation_combo)
        form.addRow("Lockout threshold", self.lockout_combo)
        form.addRow("Audit retention", self.audit_retention_combo)

        self.save_button = QPushButton("Save Settings")
        self.feedback_label = QLabel(
            "Settings changes are applied as configuration intent for the current environment."
        )
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet(
            "background-color: #eef7f2; color: #1b5e20; border: 1px solid #c9e7d1; "
            "border-radius: 10px; padding: 8px 10px;"
        )

        root.addWidget(heading)
        root.addWidget(copy)
        root.addLayout(form)
        root.addWidget(self.save_button, alignment=Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.feedback_label)
        root.addStretch(1)

        self.save_button.clicked.connect(self._save_settings)

    def _save_settings(self) -> None:
        summary = (
            f"timeout={self.session_timeout_combo.currentText()}, "
            f"rotation={self.password_rotation_combo.currentText()}, "
            f"lockout={self.lockout_combo.currentText()}, "
            f"retention={self.audit_retention_combo.currentText()}"
        )
        if self._on_admin_change is not None:
            self._on_admin_change("update_admin_settings", summary)
        self.feedback_label.setText(
            f"Saved admin settings: {summary}."
        )


class StoreEditorDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        user_management_service: AdminUserManagementService,
        initial_values: dict[str, object] | None,
        on_submit: Callable[[dict[str, object]], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_management_service = user_management_service
        self._on_submit = on_submit
        is_editing = bool(initial_values)
        values = initial_values or {}
        self._existing_store_admin_user_id = str(values.get("store_admin_user_id", "") or "")
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(980, 760)
        self.setMinimumSize(920, 680)
        self.setStyleSheet(
            "QDialog { background-color: #fbf7f1; color: #1f2933; } "
            "QScrollArea { background: transparent; border: none; } "
            "QWidget#StoreEditorScrollContent { background: transparent; } "
            "QFrame#EditorCard { background-color: #fffdf9; border: 1px solid #e4d8c9; border-radius: 18px; } "
            "QLabel#DialogHeading { font-size: 22px; font-weight: 700; color: #102a43; } "
            "QLabel#DialogCopy { font-size: 13px; color: #52606d; } "
            "QLabel#SectionTitle { font-size: 16px; font-weight: 700; color: #102a43; } "
            "QLabel#SectionCopy { font-size: 12px; color: #6b7280; } "
            "QLabel#FieldLabel { font-size: 13px; font-weight: 600; color: #334e68; padding-top: 10px; } "
            "QLabel#InlineNote { background-color: #eef6f2; color: #245247; border: 1px solid #cfe2d8; "
            "border-radius: 12px; padding: 10px 12px; } "
            "QLabel#FeedbackBanner { background-color: #fffaeb; color: #8b5a2b; border: 1px solid #e6d7c5; "
            "border-radius: 12px; padding: 10px 12px; } "
            "QLineEdit, QComboBox { background-color: white; color: #102a43; border: 1px solid #cfd8e3; "
            "border-radius: 12px; padding: 10px 12px; placeholder-text-color: #829ab1; } "
            "QLineEdit:focus, QComboBox:focus { border: 1px solid #174c4f; } "
            "QComboBox::drop-down { border: none; width: 28px; } "
            "QComboBox QAbstractItemView { background-color: white; color: #102a43; border: 1px solid #cfd8e3; "
            "selection-background-color: #dbe8df; selection-color: #102a43; } "
            "QLineEdit[readOnly=\"true\"] { background-color: #f5efe7; color: #5e584f; border: 1px solid #d9cfbf; } "
            "QPushButton#SecondaryDialogButton { background-color: #fffdf9; color: #174c4f; border: 1px solid #c6d5cf; "
            "border-radius: 12px; padding: 0 18px; font-weight: 600; } "
            "QPushButton#SecondaryDialogButton:hover { background-color: #f3f8f5; } "
            "QPushButton#PrimaryDialogButton { background-color: #174c4f; color: white; border: 1px solid #174c4f; "
            "border-radius: 12px; padding: 0 18px; font-weight: 600; } "
            "QPushButton#PrimaryDialogButton:hover { background-color: #123d40; border-color: #123d40; } "
            "QPushButton#PrimaryDialogButton:pressed { background-color: #103638; border-color: #103638; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        heading = QLabel(title)
        heading.setObjectName("DialogHeading")
        copy = QLabel(
            "Review the selected store record, update owner contact details, and manage the linked store-admin account."
            if is_editing
            else "Create a store, capture the owner contact information, and provision the initial store-admin user."
        )
        copy.setWordWrap(True)
        copy.setObjectName("DialogCopy")

        title_block = QVBoxLayout()
        title_block.setSpacing(6)
        title_block.addWidget(heading)
        title_block.addWidget(copy)

        header_row = QHBoxLayout()
        header_row.setSpacing(14)
        header_row.addLayout(title_block, stretch=1)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("SecondaryDialogButton")
        cancel_button.setMinimumHeight(44)
        cancel_button.setMinimumWidth(120)
        submit_button = QPushButton("Update Store" if is_editing else "Create Store")
        submit_button.setObjectName("PrimaryDialogButton")
        submit_button.setMinimumHeight(44)
        submit_button.setMinimumWidth(148)
        submit_button.setDefault(True)
        header_row.addWidget(cancel_button)
        header_row.addWidget(submit_button)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_content.setObjectName("StoreEditorScrollContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        cards_grid = QGridLayout()
        cards_grid.setContentsMargins(0, 0, 0, 0)
        cards_grid.setHorizontalSpacing(16)
        cards_grid.setVerticalSpacing(16)
        cards_grid.setColumnStretch(0, 1)
        cards_grid.setColumnStretch(1, 1)

        self.store_code_input = QLineEdit()
        self.store_name_input = QLineEdit()
        self.address_input = QLineEdit()
        self.city_input = QLineEdit()
        self.manager_name_input = QLineEdit()
        self.contact_info_input = QLineEdit()
        self.status_combo = QComboBox()
        self._store_status_options = ("Active", "Inactive")
        self.status_combo.addItems(list(self._store_status_options))
        self.status_combo.setMinimumHeight(44)
        self.status_combo.setMaxVisibleItems(len(self._store_status_options))
        self.created_on_input = QLineEdit()
        self.created_on_input.setReadOnly(True)
        self.updated_on_input = QLineEdit()
        self.updated_on_input.setReadOnly(True)

        self.owner_name_input = QLineEdit()
        self.owner_mobile_input = QLineEdit()
        self.owner_email_input = QLineEdit()

        self.store_admin_full_name_input = QLineEdit()
        self.store_admin_username_input = QLineEdit()
        self.store_admin_mobile_input = QLineEdit()
        self.store_admin_email_input = QLineEdit()
        self.store_admin_role_input = QLineEdit("Admin")
        self.store_admin_role_input.setReadOnly(True)

        for field, placeholder in (
            (self.store_code_input, "e.g. ST-PUN"),
            (self.store_name_input, "Enter the store display name"),
            (self.address_input, "Street, area, and landmark"),
            (self.city_input, "Primary operating city"),
            (self.manager_name_input, "Store manager or primary lead"),
            (self.contact_info_input, "Front desk phone or shared email"),
            (self.owner_name_input, "Owner full name"),
            (self.owner_mobile_input, "Primary mobile number"),
            (self.owner_email_input, "owner@company.com"),
            (self.store_admin_full_name_input, "Store admin full name"),
            (self.store_admin_username_input, "Unique username for login"),
            (self.store_admin_mobile_input, "Admin mobile number"),
            (self.store_admin_email_input, "admin@store.com"),
        ):
            self._configure_text_input(field, placeholder=placeholder)
        for field in (self.created_on_input, self.updated_on_input, self.store_admin_role_input):
            self._configure_text_input(field)

        store_form = self._create_form_layout()
        store_form.addRow(self._create_form_label("Store code"), self.store_code_input)
        store_form.addRow(self._create_form_label("Store name"), self.store_name_input)
        store_form.addRow(self._create_form_label("Address"), self.address_input)
        store_form.addRow(self._create_form_label("City"), self.city_input)
        store_form.addRow(self._create_form_label("Manager"), self.manager_name_input)
        store_form.addRow(self._create_form_label("Store contact"), self.contact_info_input)
        store_form.addRow(self._create_form_label("Status"), self.status_combo)

        owner_form = self._create_form_layout()
        owner_form.addRow(self._create_form_label("Owner name"), self.owner_name_input)
        owner_form.addRow(self._create_form_label("Owner mobile"), self.owner_mobile_input)
        owner_form.addRow(self._create_form_label("Owner email"), self.owner_email_input)

        self.store_admin_note_label = QLabel("")
        self.store_admin_note_label.setWordWrap(True)
        self.store_admin_note_label.setObjectName("InlineNote")
        admin_form = self._create_form_layout()
        admin_form.addRow(self._create_form_label("Admin role"), self.store_admin_role_input)
        admin_form.addRow(self._create_form_label("Admin name"), self.store_admin_full_name_input)
        admin_form.addRow(self._create_form_label("Admin username"), self.store_admin_username_input)
        admin_form.addRow(self._create_form_label("Admin mobile"), self.store_admin_mobile_input)
        admin_form.addRow(self._create_form_label("Admin email"), self.store_admin_email_input)
        admin_form_widget = QWidget()
        admin_form_widget.setLayout(admin_form)
        admin_panel = QWidget()
        admin_panel_layout = QVBoxLayout(admin_panel)
        admin_panel_layout.setContentsMargins(0, 0, 0, 0)
        admin_panel_layout.setSpacing(12)
        admin_panel_layout.addWidget(self.store_admin_note_label)
        admin_panel_layout.addWidget(admin_form_widget)

        metadata_form = self._create_form_layout()
        metadata_form.addRow(self._create_form_label("Created on"), self.created_on_input)
        metadata_form.addRow(self._create_form_label("Last updated"), self.updated_on_input)

        self.feedback_label = QLabel("")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setObjectName("FeedbackBanner")
        self.feedback_label.hide()

        root.addLayout(header_row)
        cards_grid.addWidget(
            self._create_section_card(
                title="Store Profile",
                copy="Operational identity, location, manager assignment, and the main store contact used by the team.",
                content=self._wrap_form(store_form),
            ),
            0,
            0,
        )
        cards_grid.addWidget(
            self._create_section_card(
                title="Store Owner",
                copy="Owner details used for approvals, escalation paths, and direct communication.",
                content=self._wrap_form(owner_form),
            ),
            0,
            1,
        )
        cards_grid.addWidget(
            self._create_section_card(
                title="Store Admin User",
                copy="Primary administrator account linked to this store. This user manages the store after provisioning.",
                content=admin_panel,
            ),
            1,
            0,
        )
        cards_grid.addWidget(
            self._create_section_card(
                title="Record Metadata",
                copy="System-managed timestamps for the store record. These fields update automatically.",
                content=self._wrap_form(metadata_form),
            ),
            1,
            1,
        )
        scroll_layout.addLayout(cards_grid)
        scroll_layout.addStretch(1)
        scroll_area.setWidget(scroll_content)
        root.addWidget(scroll_area, stretch=1)
        root.addWidget(self.feedback_label)
        self.store_code_input.setText(str(values.get("store_code", "")))
        self.store_name_input.setText(str(values.get("store_name", "")))
        self.address_input.setText(str(values.get("address", "")))
        self.city_input.setText(str(values.get("city", "")))
        self.manager_name_input.setText(str(values.get("manager_name", "")))
        self.contact_info_input.setText(str(values.get("contact_info", "")))
        self.owner_name_input.setText(str(values.get("owner_name", "")))
        self.owner_mobile_input.setText(str(values.get("owner_mobile", "")))
        self.owner_email_input.setText(str(values.get("owner_email", "")))
        self.store_admin_full_name_input.setText(str(values.get("store_admin_full_name", "")))
        self.store_admin_username_input.setText(str(values.get("store_admin_username", "")))
        self.store_admin_mobile_input.setText(str(values.get("store_admin_mobile", "")))
        self.store_admin_email_input.setText(str(values.get("store_admin_email", "")))
        initial_status = str(values.get("status", "Active"))
        if initial_status not in self._store_status_options:
            initial_status = "Active"
        self.status_combo.setCurrentText(initial_status)
        self.created_on_input.setText(
            str(values.get("created_on", "Set automatically when the store is created"))
        )
        self.updated_on_input.setText(
            str(values.get("updated_on", "Updated automatically after save"))
        )
        if self._existing_store_admin_user_id:
            self.store_admin_username_input.setReadOnly(True)
            self.store_admin_username_input.setClearButtonEnabled(False)
            self.store_admin_note_label.setText(
                "This store is already linked to an Admin user. Username stays fixed here; update the remaining contact details as needed."
            )
        else:
            self.store_admin_note_label.setText(
                "Creating the store will also create an Admin user for that store. The default password follows @ct<username>123456789 and the first sign-in will force a reset."
            )

        cancel_button.clicked.connect(self.reject)
        submit_button.clicked.connect(self._submit)

    def _configure_text_input(self, field: QLineEdit, *, placeholder: str = "") -> None:
        field.setMinimumHeight(44)
        field.setClearButtonEnabled(not field.isReadOnly())
        if placeholder:
            field.setPlaceholderText(placeholder)

    def _create_form_layout(self) -> QFormLayout:
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)
        return form

    def _create_form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        label.setMinimumWidth(132)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        return label

    def _wrap_form(self, form: QFormLayout) -> QWidget:
        container = QWidget()
        container.setLayout(form)
        return container

    def _create_section_card(self, *, title: str, copy: str, content: QWidget) -> QFrame:
        card = QFrame()
        card.setObjectName("EditorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        copy_label = QLabel(copy)
        copy_label.setObjectName("SectionCopy")
        copy_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(copy_label)
        layout.addWidget(content)
        layout.addStretch(1)
        return card

    def _submit(self) -> None:
        payload = {
            "store_code": self.store_code_input.text().strip(),
            "store_name": self.store_name_input.text().strip(),
            "address": self.address_input.text().strip(),
            "city": self.city_input.text().strip(),
            "manager_name": self.manager_name_input.text().strip(),
            "contact_info": self.contact_info_input.text().strip(),
            "owner_name": self.owner_name_input.text().strip(),
            "owner_mobile": self.owner_mobile_input.text().strip(),
            "owner_email": self.owner_email_input.text().strip(),
            "status": self.status_combo.currentText(),
            "store_admin_full_name": self.store_admin_full_name_input.text().strip(),
            "store_admin_username": self.store_admin_username_input.text().strip(),
            "store_admin_mobile": self.store_admin_mobile_input.text().strip(),
            "store_admin_email": self.store_admin_email_input.text().strip(),
        }
        try:
            self._on_submit(payload)
        except ValueError as exc:
            self.feedback_label.setText(str(exc))
            self.feedback_label.show()
            return

        self.accept()


class RoleEditorDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        initial_values: dict[str, object] | None,
        on_submit: Callable[[dict[str, object]], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_submit = on_submit
        is_editing = bool(initial_values)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(760, 620)
        self.setStyleSheet(
            "QDialog { background-color: #fffaf3; color: #1f2933; } "
            "QLabel { color: #1f2933; } "
            "QLineEdit, QComboBox, QPlainTextEdit { background-color: white; color: #1f2933; "
            "border: 1px solid #d7c9b8; border-radius: 10px; padding: 8px 10px; } "
            "QComboBox QAbstractItemView { background-color: white; color: #1f2933; "
            "border: 1px solid #d7c9b8; selection-background-color: #dbe8df; "
            "selection-color: #1f2933; } "
            "QLineEdit[readOnly=\"true\"] { background-color: #f4ede3; color: #5e584f; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 20px; font-weight: 700; color: #1f2933;")
        copy = QLabel(
            "Review the selected role definition, adjust scope or permissions, and save the update."
            if is_editing
            else "Create a new role definition for the superadmin catalog."
        )
        copy.setWordWrap(True)
        copy.setStyleSheet("color: #5e584f;")

        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        title_block.addWidget(heading)
        title_block.addWidget(copy)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_row.addLayout(title_block, stretch=1)

        cancel_button = QPushButton("Cancel")
        cancel_button.setMinimumHeight(38)
        cancel_button.setStyleSheet(
            "background-color: #efe5d9; color: #1f2933; border: 1px solid #d7c9b8;"
        )
        submit_button = QPushButton("Update" if is_editing else "Create")
        submit_button.setMinimumHeight(38)
        submit_button.setStyleSheet(
            "background-color: #174c4f; color: white; border: 1px solid #174c4f; padding: 0 16px;"
        )
        header_row.addWidget(cancel_button)
        header_row.addWidget(submit_button)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.role_name_input = QLineEdit()
        self.scope_input = QLineEdit()
        self.description_input = QPlainTextEdit()
        self.description_input.setPlaceholderText("Describe what this role is responsible for.")
        self.description_input.setFixedHeight(90)
        self.permissions_input = QPlainTextEdit()
        self.permissions_input.setPlaceholderText("Enter one permission per line or comma-separated values.")
        self.permissions_input.setFixedHeight(120)
        self.status_combo = QComboBox()
        self._role_status_options = ("Active", "Inactive")
        self.status_combo.addItems(list(self._role_status_options))
        self.status_combo.setMinimumHeight(42)
        self.status_combo.setMaxVisibleItems(len(self._role_status_options))
        self.status_combo.setStyleSheet(
            "QComboBox { background-color: white; color: #1f2933; border: 1px solid #d7c9b8; "
            "border-radius: 10px; padding: 8px 10px; } "
            "QComboBox QAbstractItemView { background-color: white; color: #1f2933; "
            "border: 1px solid #d7c9b8; selection-background-color: #dbe8df; "
            "selection-color: #1f2933; }"
        )
        self.created_on_input = QLineEdit()
        self.created_on_input.setReadOnly(True)
        self.updated_on_input = QLineEdit()
        self.updated_on_input.setReadOnly(True)

        form.addRow("Role name", self.role_name_input)
        form.addRow("Scope", self.scope_input)
        form.addRow("Description", self.description_input)
        form.addRow("Permissions", self.permissions_input)
        form.addRow("Status", self.status_combo)
        form.addRow("Created on", self.created_on_input)
        form.addRow("Last updated", self.updated_on_input)

        self.feedback_label = QLabel("")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet(
            "background-color: #fffaeb; color: #8b5a2b; border: 1px solid #e6d7c5; "
            "border-radius: 10px; padding: 8px 10px;"
        )
        self.feedback_label.hide()

        root.addLayout(header_row)
        root.addLayout(form)
        root.addWidget(self.feedback_label)
        root.addStretch(1)

        values = initial_values or {}
        self.role_name_input.setText(str(values.get("role_name", "")))
        self.role_name_input.setReadOnly(bool(values))
        self.scope_input.setText(str(values.get("scope", "")))
        self.description_input.setPlainText(str(values.get("description", "")))
        self.permissions_input.setPlainText(
            "\n".join(values.get("permissions", []))
            if isinstance(values.get("permissions"), tuple | list)
            else str(values.get("permissions", ""))
        )
        initial_status = "Active" if values.get("is_active", True) else "Inactive"
        if initial_status not in self._role_status_options:
            initial_status = "Active"
        self.status_combo.setCurrentText(initial_status)
        self.created_on_input.setText(
            str(values.get("created_on", "Set automatically when the role is created"))
        )
        self.updated_on_input.setText(
            str(values.get("updated_on", "Updated automatically after save"))
        )

        cancel_button.clicked.connect(self.reject)
        submit_button.clicked.connect(self._submit)

    def _submit(self) -> None:
        permission_values = [
            value.strip()
            for value in re.split(r"[\n,;|]+", self.permissions_input.toPlainText())
            if value.strip()
        ]
        payload = {
            "role_name": self.role_name_input.text().strip(),
            "scope": self.scope_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "permissions": permission_values,
            "is_active": self.status_combo.currentText() == "Active",
        }
        try:
            self._on_submit(payload)
        except ValueError as exc:
            self.feedback_label.setText(str(exc))
            self.feedback_label.show()
            return

        self.accept()


class SuperadminDashboardScreen(QWidget):
    def __init__(
        self,
        *,
        user_management_service: AdminUserManagementService,
        on_admin_change: Callable[[str, str], None] | None = None,
        on_permission_change: Callable[[str, str], None] | None = None,
        on_catalog_change: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_management_service = user_management_service
        self._on_admin_change = on_admin_change
        self._on_permission_change = on_permission_change
        self._on_catalog_change = on_catalog_change
        self._active_catalog = "stores"
        self._store_lookup_by_code: dict[str, str] = {}
        self._role_lookup_by_name: dict[str, str] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        dashboard_action_button_style = (
            "QPushButton { background-color: #174c4f; color: white; border: 1px solid #174c4f; "
            "border-radius: 12px; padding: 0 18px; font-weight: 600; } "
            "QPushButton:hover { background-color: #123d40; border: 1px solid #123d40; } "
            "QPushButton:pressed { background-color: #0f3739; border: 1px solid #0f3739; }"
        )

        switcher = QHBoxLayout()
        switcher.setSpacing(10)
        self.stores_button = QPushButton("Store Management")
        self.roles_button = QPushButton("Role Management")
        for button in (self.stores_button, self.roles_button):
            button.setCheckable(True)
            button.setMinimumHeight(40)
            button.setStyleSheet(
                "QPushButton { background-color: #efe5d9; color: #1f2933; border: 1px solid #d7c9b8; } "
                "QPushButton:checked { background-color: #174c4f; color: white; border: 1px solid #174c4f; }"
            )
            switcher.addWidget(button)
        switcher.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setMinimumHeight(40)
        self.refresh_button.setStyleSheet(dashboard_action_button_style)
        self.create_button = QPushButton("Create Store")
        self.create_button.setMinimumHeight(40)
        self.create_button.setStyleSheet(dashboard_action_button_style)
        action_row.addStretch(1)
        action_row.addWidget(self.refresh_button)
        action_row.addWidget(self.create_button)

        self.store_screen = ManagementGridScreen(
            title="Stores",
            subtitle="Select a store row to open the editing popup. Superadmin can also create new stores from this panel.",
            headers=["Store Name", "Store Code", "City", "Status", "Created On"],
            rows=[],
            filter_label="Status",
            filter_column=3,
            filter_options=["Active", "Inactive"],
            search_placeholder="Search stores...",
            show_header=False,
            show_status=False,
            show_search=False,
            compact_controls=True,
            sync_filter_options_from_rows=True,
            default_sort_column=0,
            parent=self,
        )
        self.role_screen = ManagementGridScreen(
            title="Roles",
            subtitle="Select a role row to open the editing popup. Superadmin can create and adjust role definitions here.",
            headers=["Role Name", "Scope", "Status", "Created On"],
            rows=[],
            filter_label="Status",
            filter_column=2,
            filter_options=["Active", "Inactive"],
            search_placeholder="Search roles...",
            show_header=False,
            show_status=False,
            show_search=False,
            compact_controls=True,
            sync_filter_options_from_rows=True,
            default_sort_column=0,
            parent=self,
        )

        self.catalog_stack = QStackedWidget()
        self.catalog_stack.addWidget(self.store_screen)
        self.catalog_stack.addWidget(self.role_screen)

        self.feedback_label = QLabel(
            "Stores load by default. Click any row to open the matching store or role editor."
        )
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet(
            "background-color: #eef7f2; color: #125d3f; border: 1px solid #c9e7d1; "
            "border-radius: 10px; padding: 8px 10px; font-weight: 600;"
        )

        root.addLayout(switcher)
        root.addLayout(action_row)
        root.addWidget(self.catalog_stack, stretch=1)
        root.addWidget(self.feedback_label)

        self.stores_button.clicked.connect(lambda: self._show_catalog("stores"))
        self.roles_button.clicked.connect(lambda: self._show_catalog("roles"))
        self.create_button.clicked.connect(self._create_current_record)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.store_screen.table.doubleClicked.connect(self._open_store_from_index)
        self.role_screen.table.doubleClicked.connect(self._open_role_from_index)

        self.refresh_data()
        self._show_catalog("stores")

    def refresh_data(self) -> None:
        self._refresh_store_rows()
        self._refresh_role_rows()
        self._update_catalog_summary()

    def _refresh_store_rows(self) -> None:
        store_records = self._user_management_service.list_stores()
        self._store_lookup_by_code = {
            record.store_code: record.store_id
            for record in store_records
        }
        self.store_screen.update_rows(
            [
                (
                    record.store_name,
                    record.store_code,
                    record.city,
                    record.status,
                    record.created_on.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                )
                for record in store_records
            ]
        )

    def _refresh_role_rows(self) -> None:
        role_records = self._user_management_service.list_role_definitions()
        self._role_lookup_by_name = {
            record.role_name: record.role_name
            for record in role_records
        }
        self.role_screen.update_rows(
            [
                (
                    record.role_name,
                    record.scope,
                    "Active" if record.is_active else "Inactive",
                    record.created_on.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                )
                for record in role_records
            ]
        )

    def _show_catalog(self, catalog_key: str) -> None:
        self._active_catalog = catalog_key
        self.stores_button.setChecked(catalog_key == "stores")
        self.roles_button.setChecked(catalog_key == "roles")
        if catalog_key == "stores":
            self.catalog_stack.setCurrentWidget(self.store_screen)
            self.create_button.setText("Create Store")
            self.feedback_label.setText(
                "Single-click any store row to highlight it, then double-click to open the store details dialog."
            )
        else:
            self.catalog_stack.setCurrentWidget(self.role_screen)
            self.create_button.setText("Create Role")
            self.feedback_label.setText(
                "Single-click any role row to highlight it, then double-click to open the role details dialog."
            )
        self._update_catalog_summary()

    def _update_catalog_summary(self) -> None:
        return

    def _create_current_record(self) -> None:
        if self._active_catalog == "stores":
            self._open_store_dialog()
            return
        self._open_role_dialog()

    def _open_store_from_index(self, index: QModelIndex) -> None:
        row_values = self.store_screen.row_values_for_index(index)
        if row_values is None:
            return
        store_id = self._store_lookup_by_code.get(row_values[1])
        if store_id is None:
            return
        self._open_store_dialog(store_id=store_id)

    def _open_role_from_index(self, index: QModelIndex) -> None:
        row_values = self.role_screen.row_values_for_index(index)
        if row_values is None:
            return
        role_name = self._role_lookup_by_name.get(row_values[0])
        if role_name is None:
            return
        self._open_role_dialog(role_name=role_name)

    def _open_store_dialog(self, *, store_id: str | None = None) -> None:
        record = self._user_management_service.get_store(store_id) if store_id else None

        def handle_submit(payload: dict[str, object]) -> None:
            if record is None:
                result = self._user_management_service.create_store_with_admin(
                    store_code=str(payload["store_code"]),
                    store_name=str(payload["store_name"]),
                    address=str(payload["address"]),
                    city=str(payload["city"]),
                    manager_name=str(payload["manager_name"]),
                    contact_info=str(payload["contact_info"]),
                    owner_name=str(payload["owner_name"]),
                    owner_mobile=str(payload["owner_mobile"]),
                    owner_email=str(payload["owner_email"]),
                    status=str(payload["status"]),
                    store_admin_username=str(payload["store_admin_username"]),
                    store_admin_full_name=str(payload["store_admin_full_name"]),
                    store_admin_mobile=str(payload["store_admin_mobile"]),
                    store_admin_email=str(payload["store_admin_email"]),
                )
                if self._on_admin_change is not None:
                    self._on_admin_change(
                        "create_store",
                        f"{result.store_id}:{payload['store_code']}:{payload['store_name']}",
                    )
                    if result.store_admin_user_id and result.store_admin_username:
                        self._on_admin_change(
                            "create_store_admin_user",
                            f"{result.store_admin_user_id}:{result.store_admin_username}:Admin",
                        )
                feedback_message = (
                    f"Created store {payload['store_name']} ({payload['store_code']}). "
                    f"Store admin {result.store_admin_username} was provisioned with temporary password "
                    f"{result.temporary_password}."
                )
            else:
                result = self._user_management_service.update_store_with_admin(
                    store_id=record.store_id,
                    store_code=str(payload["store_code"]),
                    store_name=str(payload["store_name"]),
                    address=str(payload["address"]),
                    city=str(payload["city"]),
                    manager_name=str(payload["manager_name"]),
                    contact_info=str(payload["contact_info"]),
                    owner_name=str(payload["owner_name"]),
                    owner_mobile=str(payload["owner_mobile"]),
                    owner_email=str(payload["owner_email"]),
                    status=str(payload["status"]),
                    store_admin_username=str(payload["store_admin_username"]),
                    store_admin_full_name=str(payload["store_admin_full_name"]),
                    store_admin_mobile=str(payload["store_admin_mobile"]),
                    store_admin_email=str(payload["store_admin_email"]),
                )
                if self._on_admin_change is not None:
                    self._on_admin_change(
                        "update_store",
                        f"{record.store_id}:{payload['store_code']}:{payload['store_name']}",
                    )
                    if result.temporary_password and result.store_admin_user_id and result.store_admin_username:
                        self._on_admin_change(
                            "create_store_admin_user",
                            f"{result.store_admin_user_id}:{result.store_admin_username}:Admin",
                        )
                    elif result.store_admin_user_id and result.store_admin_username:
                        self._on_admin_change(
                            "update_store_admin_user",
                            f"{result.store_admin_user_id}:{result.store_admin_username}:Admin",
                        )
                feedback_message = (
                    f"Updated store {payload['store_name']} ({payload['store_code']})."
                )
                if result.temporary_password and result.store_admin_username:
                    feedback_message += (
                        f" A new store admin {result.store_admin_username} was created with temporary password "
                        f"{result.temporary_password}."
                    )
            self.feedback_label.setText(feedback_message)
            self.refresh_data()
            if self._on_catalog_change is not None:
                self._on_catalog_change()

        dialog = StoreEditorDialog(
            title="Create Store" if record is None else f"Store Details | {record.store_code}",
            user_management_service=self._user_management_service,
            initial_values=(
                None
                if record is None
                else {
                    "store_code": record.store_code,
                    "store_name": record.store_name,
                    "address": record.address,
                    "city": record.city,
                    "manager_name": record.manager_name,
                    "contact_info": record.contact_info,
                    "owner_name": record.owner_name,
                    "owner_mobile": record.owner_mobile,
                    "owner_email": record.owner_email,
                    "store_admin_user_id": record.store_admin_user_id or "",
                    "store_admin_username": record.store_admin_username,
                    "store_admin_full_name": record.store_admin_full_name,
                    "store_admin_mobile": record.store_admin_mobile,
                    "store_admin_email": record.store_admin_email,
                    "status": record.status,
                    "created_on": record.created_on.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "updated_on": record.updated_on.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                }
            ),
            on_submit=handle_submit,
            parent=self,
        )
        dialog.exec()

    def _open_role_dialog(self, *, role_name: str | None = None) -> None:
        record = self._user_management_service.get_role_definition(role_name or "") if role_name else None

        def handle_submit(payload: dict[str, object]) -> None:
            permission_values = [str(value) for value in payload["permissions"]]
            if record is None:
                created_role_name = self._user_management_service.create_role_definition(
                    role_name=str(payload["role_name"]),
                    scope=str(payload["scope"]),
                    description=str(payload["description"]),
                    permissions=permission_values,
                    is_active=bool(payload["is_active"]),
                )
                if self._on_admin_change is not None:
                    self._on_admin_change(
                        "create_role_definition",
                        f"{created_role_name}:{payload['scope']}",
                    )
                if self._on_permission_change is not None:
                    self._on_permission_change(
                        "create_role_definition_permissions",
                        f"{created_role_name}:{', '.join(permission_values)}",
                    )
                self.feedback_label.setText(f"Created role definition {created_role_name}.")
            else:
                self._user_management_service.update_role_definition(
                    role_name=record.role_name,
                    scope=str(payload["scope"]),
                    description=str(payload["description"]),
                    permissions=permission_values,
                    is_active=bool(payload["is_active"]),
                )
                if self._on_admin_change is not None:
                    self._on_admin_change(
                        "update_role_definition",
                        f"{record.role_name}:{payload['scope']}",
                    )
                if self._on_permission_change is not None:
                    self._on_permission_change(
                        "update_role_definition_permissions",
                        f"{record.role_name}:{', '.join(permission_values)}",
                    )
                self.feedback_label.setText(f"Updated role definition {record.role_name}.")
            self.refresh_data()
            if self._on_catalog_change is not None:
                self._on_catalog_change()

        dialog = RoleEditorDialog(
            title="Create Role" if record is None else f"Role Details | {record.role_name}",
            initial_values=(
                None
                if record is None
                else {
                    "role_name": record.role_name,
                    "scope": record.scope,
                    "description": record.description,
                    "permissions": list(record.permissions),
                    "is_active": record.is_active,
                    "created_on": record.created_on.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "updated_on": record.updated_on.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                }
            ),
            on_submit=handle_submit,
            parent=self,
        )
        dialog.exec()

    def _permission_preview(self, permissions: tuple[str, ...]) -> str:
        if not permissions:
            return "No permissions"
        if len(permissions) <= 3:
            return ", ".join(permissions)
        return f"{', '.join(permissions[:3])}, +{len(permissions) - 3} more"


class AssignmentWorkspace(QWidget):
    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        source_label: str,
        target_label: str,
        source_items: list[str],
        target_items: list[str],
        on_assignment_change: Callable[[str, str], None] | None = None,
        on_back: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_assignment_change = on_assignment_change
        self._on_back = on_back

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        subheading = QLabel(subtitle)
        subheading.setWordWrap(True)
        subheading.setStyleSheet("color: #555;")

        labels = QFormLayout()
        labels.addRow("Source", QLabel(source_label))
        labels.addRow("Assigned", QLabel(target_label))

        splitter = QSplitter()
        self.available_list = QListWidget()
        self.available_list.addItems(source_items)

        self.assigned_list = QListWidget()
        self.assigned_list.addItems(target_items)

        transfer_controls = QWidget()
        transfer_layout = QVBoxLayout(transfer_controls)
        transfer_layout.addStretch(1)

        self.assign_button = QPushButton("Assign ->")
        self.unassign_button = QPushButton("<- Remove")
        transfer_layout.addWidget(self.assign_button)
        transfer_layout.addWidget(self.unassign_button)
        transfer_layout.addStretch(1)

        splitter.addWidget(self.available_list)
        splitter.addWidget(transfer_controls)
        splitter.addWidget(self.assigned_list)
        splitter.setSizes([280, 120, 280])

        self.feedback_label = QLabel(
            "Use the transfer controls to update assignments without leaving the current window."
        )
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet(
            "background-color: #fffaeb; color: #8b5a2b; border: 1px solid #e6d7c5; "
            "border-radius: 10px; padding: 8px 10px;"
        )

        actions = QHBoxLayout()
        self.back_button = QPushButton("Back to Admin")
        self.back_button.clicked.connect(self._go_back)
        actions.addWidget(self.back_button)
        actions.addStretch(1)

        root.addWidget(heading)
        root.addWidget(subheading)
        root.addLayout(labels)
        root.addWidget(splitter)
        root.addWidget(self.feedback_label)
        root.addLayout(actions)

        self.assign_button.clicked.connect(self._assign_selected)
        self.unassign_button.clicked.connect(self._unassign_selected)

    def _assign_selected(self) -> None:
        current = self.available_list.currentItem()
        if current is None:
            self.feedback_label.setText("Select a source item before assigning it.")
            return
        self._move_item(current, self.available_list, self.assigned_list, "assign")

    def _unassign_selected(self) -> None:
        current = self.assigned_list.currentItem()
        if current is None:
            self.feedback_label.setText("Select an assigned item before removing it.")
            return
        self._move_item(current, self.assigned_list, self.available_list, "unassign")

    def _move_item(
        self,
        item: QListWidgetItem,
        origin: QListWidget,
        destination: QListWidget,
        action: str,
    ) -> None:
        text = item.text()
        origin.takeItem(origin.row(item))
        destination.addItem(text)
        if self._on_assignment_change:
            self._on_assignment_change(action, text)
        verb = "Assigned" if action == "assign" else "Removed"
        self.feedback_label.setText(f"{verb} {text}. Changes were recorded in the audit trail.")

    def _go_back(self) -> None:
        if self._on_back is not None:
            self._on_back()


class UserRoleAssignmentWorkspace(AssignmentWorkspace):
    def __init__(
        self,
        on_assignment_change: Callable[[str, str], None] | None = None,
        on_back: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title="Assign Roles to User",
            subtitle="Review a user's effective access and update assignments in the same admin view.",
            source_label="Available roles",
            target_label="User roles",
            source_items=["Billing Analyst", "Support Agent", "Audit Reader", "Security Officer"],
            target_items=["System Admin"],
            on_assignment_change=on_assignment_change,
            on_back=on_back,
            parent=parent,
        )


class RolePermissionAssignmentWorkspace(AssignmentWorkspace):
    def __init__(
        self,
        on_assignment_change: Callable[[str, str], None] | None = None,
        on_back: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title="Assign Permissions to Role",
            subtitle="Adjust role capabilities in place and keep permission changes on the audit timeline.",
            source_label="Available permissions",
            target_label="Role permissions",
            source_items=[
                "user:create",
                "user:disable",
                "role:assign",
                "report:download",
                "billing:refund",
            ],
            target_items=["user:view", "user:edit", "permission:view"],
            on_assignment_change=on_assignment_change,
            on_back=on_back,
            parent=parent,
        )


class AccessControlWorkspace(QWidget):
    def __init__(
        self,
        *,
        current_user_id: str | None,
        audit_service: AuditService,
        audit_review_service: AuditReviewService,
        user_management_service: AdminUserManagementService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._current_user_id = current_user_id
        self._audit_service = audit_service
        self._user_management_service = user_management_service

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.heading = QLabel("Access Control Management")
        self.heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.subtitle = QLabel(
            "Use the overview tabs for audit and policy review, then switch into focused admin workspaces from the horizontal submenu."
        )
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet("color: #555;")

        self.section_nav_panel = QWidget()
        submenu = QHBoxLayout(self.section_nav_panel)
        submenu.setContentsMargins(0, 0, 0, 0)
        submenu.setSpacing(10)

        self.dashboard_button = QPushButton("Dashboard")
        self.overview_button = QPushButton("Overview")
        self.manage_users_button = QPushButton("Manage Users")
        self.settings_button = QPushButton("Settings")

        self._section_buttons = {
            "dashboard": self.dashboard_button,
            "overview": self.overview_button,
            "manage_users": self.manage_users_button,
            "settings": self.settings_button,
        }
        for button in self._section_buttons.values():
            button.setCheckable(True)
            button.setMinimumHeight(40)
            button.setStyleSheet(
                "QPushButton { background-color: #efe5d9; color: #1f2933; } "
                "QPushButton:checked { background-color: #174c4f; color: white; }"
            )
            submenu.addWidget(button)
        submenu.addStretch(1)

        self.section_stack = QStackedWidget()
        self.dashboard_page = SuperadminDashboardScreen(
            user_management_service=self._user_management_service,
            on_admin_change=self._record_admin_change,
            on_permission_change=self._record_permission_change,
            on_catalog_change=self._refresh_catalog_backed_views,
            parent=self,
        )
        self.overview_page = self._build_overview_page(audit_review_service)
        self.manage_users_page = ManageUsersScreen(
            current_user_id=self._current_user_id,
            user_management_service=self._user_management_service,
            on_admin_change=self._record_admin_change,
            on_permission_change=self._record_permission_change,
            parent=self,
        )
        self.settings_page = AdminSettingsScreen(
            on_admin_change=self._record_admin_change,
            parent=self,
        )

        self.section_stack.addWidget(self.dashboard_page)
        self.section_stack.addWidget(self.overview_page)
        self.section_stack.addWidget(self.manage_users_page)
        self.section_stack.addWidget(self.settings_page)

        root.addWidget(self.heading)
        root.addWidget(self.subtitle)
        root.addWidget(self.section_nav_panel)
        root.addWidget(self.section_stack)

        self.dashboard_button.clicked.connect(lambda: self._show_section("dashboard"))
        self.overview_button.clicked.connect(lambda: self._show_section("overview"))
        self.manage_users_button.clicked.connect(lambda: self._show_section("manage_users"))
        self.settings_button.clicked.connect(lambda: self._show_section("settings"))
        self._refresh_section_availability(reset_active_section=True)

    def _build_overview_page(self, audit_review_service: AuditReviewService) -> QWidget:
        page = QWidget(self)
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.overview_intro_label = QLabel(
            "Review user, role, permission, and audit information here before moving into focused admin subpages."
        )
        self.overview_intro_label.setWordWrap(True)
        self.overview_intro_label.setStyleSheet("color: #555;")

        self.tabs = QTabWidget()
        self.users_overview_screen = self._build_user_screen()
        self.roles_overview_screen = self._build_role_screen()
        self.permissions_overview_screen = self._build_permission_screen()
        self.tabs.addTab(self.users_overview_screen, "Users")
        self.tabs.addTab(self.roles_overview_screen, "Roles")
        self.tabs.addTab(self.permissions_overview_screen, "Permissions")
        self.tabs.addTab(AuditReviewScreen(audit_review_service), "Audit")

        root.addWidget(self.overview_intro_label)
        root.addWidget(self.tabs)
        return page

    def _build_user_screen(self) -> QWidget:
        rows = self._user_overview_rows()
        return ManagementGridScreen(
            title="User Management",
            subtitle="Review persisted managed-user records from the admin data store.",
            headers=["User ID", "Username", "Name", "Contact Information", "Created On"],
            rows=rows,
            filter_label="Created",
            filter_column=4,
            filter_options=[],
        )

    def _user_overview_rows(self) -> list[tuple[str, ...]]:
        rows: list[tuple[str, ...]] = []
        for summary in self._user_management_service.list_users(actor_user_id=self._current_user_id):
            profile = self._user_management_service.get_user_profile(summary.user_id)
            if profile is None:
                continue
            rows.append(
                (
                    profile.user_id,
                    profile.username,
                    profile.full_name,
                    profile.contact_info,
                    profile.created_on.strftime("%Y-%m-%d"),
                )
            )
        return rows

    def _build_role_screen(self) -> QWidget:
        role_definitions = self._user_management_service.list_role_definitions()
        scope_options = sorted({role.scope for role in role_definitions})
        return ManagementGridScreen(
            title="Role Management",
            subtitle="Control persisted role definitions and monitor how many users are assigned to each role.",
            headers=["Role Key", "Role Name", "Scope", "Assignments"],
            rows=self._role_overview_rows(),
            filter_label="Scope",
            filter_column=2,
            filter_options=scope_options,
        )

    def _build_permission_screen(self) -> QWidget:
        return ManagementGridScreen(
            title="Permission Management",
            subtitle="Maintain fine-grained capabilities with explicit risk levels derived from the active role catalog.",
            headers=["Permission", "Module", "Action", "Risk"],
            rows=self._permission_overview_rows(),
            filter_label="Risk",
            filter_column=3,
            filter_options=["Low", "Medium", "High", "Critical"],
        )

    def set_current_user_id(self, current_user_id: str | None) -> None:
        self._current_user_id = current_user_id
        self.manage_users_page.set_current_user_id(current_user_id)
        self._refresh_section_availability(reset_active_section=True)

    def _record_admin_change(self, action: str, value: str) -> None:
        correlation_id = ensure_correlation_id()
        self._audit_service.publish(
            event_type=AuditEventType.ADMIN_CHANGE,
            correlation_id=correlation_id,
            actor=AuditActor(actor_id=self._current_user_id),
            payload={"action": action, "target_type": "role_assignment", "value": value},
        )

    def _record_permission_change(self, action: str, value: str) -> None:
        correlation_id = ensure_correlation_id()
        self._audit_service.publish(
            event_type=AuditEventType.PERMISSION_CHANGE,
            correlation_id=correlation_id,
            actor=AuditActor(actor_id=self._current_user_id),
            payload={"action": action, "target_type": "permission_assignment", "value": value},
        )

    def _show_section(self, section_key: str) -> None:
        is_superadmin = self._user_management_service.role_name_for_user(self._current_user_id) == "Superadmin"
        if is_superadmin:
            section_key = "dashboard"
        elif section_key == "dashboard":
            section_key = "overview"

        for key, button in self._section_buttons.items():
            if button.isVisible():
                button.setChecked(key == section_key)

        if section_key == "dashboard":
            self.dashboard_page.refresh_data()
            self.subtitle.setText(
                "Superadmin dashboard exposes Store Management and Role Management in one horizontal control surface."
            )
            self.section_stack.setCurrentWidget(self.dashboard_page)
            return

        if section_key == "overview":
            self.users_overview_screen.update_rows(self._user_overview_rows())
            self.roles_overview_screen.update_rows(self._role_overview_rows())
            self.permissions_overview_screen.update_rows(self._permission_overview_rows())
            store_context = self._user_management_service.get_store_dashboard_context_for_user(
                self._current_user_id
            )
            if store_context is None:
                self.overview_intro_label.setText(
                    "Review user, role, permission, and audit information here before moving into focused admin subpages."
                )
            else:
                self.overview_intro_label.setText(
                    f"This overview is scoped to {store_context.store_name}. User listings and assignment counts reflect this store only."
                )
            self.subtitle.setText(
                "Admin Console opens on the tabbed overview so users can review Users, Roles, Permissions, and Audit data first."
            )
            self.section_stack.setCurrentWidget(self.overview_page)
            return

        if section_key == "manage_users":
            self.manage_users_page.refresh_reference_data()
            self.subtitle.setText(
                "Select a user by name, edit roles and permissions, activate or deactivate the account, reset the default password, and review day-by-day activity."
            )
            self.section_stack.setCurrentWidget(self.manage_users_page)
            return

        self.subtitle.setText(
            "Maintain session, password, lockout, and audit retention settings for the admin area."
        )
        self.section_stack.setCurrentWidget(self.settings_page)

    def _role_overview_rows(self) -> list[tuple[str, ...]]:
        assignment_counts: dict[str, int] = {}
        for summary in self._user_management_service.list_users(actor_user_id=self._current_user_id):
            profile = self._user_management_service.get_user_profile(summary.user_id)
            if profile is None:
                continue
            for role_name in profile.roles:
                assignment_counts[role_name] = assignment_counts.get(role_name, 0) + 1

        rows: list[tuple[str, ...]] = []
        for role in self._user_management_service.list_role_definitions():
            rows.append(
                (
                    role.role_name.upper().replace(" ", "_"),
                    role.role_name,
                    role.scope,
                    str(assignment_counts.get(role.role_name, 0)),
                )
            )
        return rows

    def _permission_overview_rows(self) -> list[tuple[str, ...]]:
        rows: list[tuple[str, ...]] = []
        for permission_name in self._user_management_service.permission_options():
            module, action, risk = self._permission_metadata(permission_name)
            rows.append((permission_name, module, action, risk))
        return rows

    def _permission_metadata(self, permission_name: str) -> tuple[str, str, str]:
        segments = permission_name.split(":")
        module = segments[0].replace("_", " ").title() if segments else "General"
        action = segments[-1].replace("_", " ").title() if segments else "Access"
        permission_lower = permission_name.lower()
        if any(token in permission_lower for token in ("delete", "assign", "superadmin")):
            risk = "Critical"
        elif any(token in permission_lower for token in ("create", "update", "edit", "refund")):
            risk = "High"
        elif any(token in permission_lower for token in ("view", "read", "status")):
            risk = "Low"
        else:
            risk = "Medium"
        return module, action, risk

    def _refresh_catalog_backed_views(self) -> None:
        self.users_overview_screen.update_rows(self._user_overview_rows())
        self.manage_users_page.refresh_reference_data()
        self.roles_overview_screen.update_rows(self._role_overview_rows())
        self.permissions_overview_screen.update_rows(self._permission_overview_rows())

    def _refresh_section_availability(self, *, reset_active_section: bool) -> None:
        is_superadmin = self._user_management_service.role_name_for_user(self._current_user_id) == "Superadmin"
        if is_superadmin:
            self.heading.setText("Superadmin Dashboard")
            self.heading.hide()
            self.subtitle.hide()
            self.dashboard_button.show()
            self.overview_button.hide()
            self.manage_users_button.hide()
            self.settings_button.hide()
            self.section_nav_panel.hide()
        else:
            store_context = self._user_management_service.get_store_dashboard_context_for_user(
                self._current_user_id
            )
            if store_context is None:
                self.heading.setText("Access Control Management")
            else:
                self.heading.setText(f"{store_context.store_name} Administration")
            self.heading.show()
            self.subtitle.show()
            self.dashboard_button.hide()
            self.overview_button.show()
            self.manage_users_button.show()
            self.settings_button.show()
            self.section_nav_panel.show()

        if reset_active_section:
            self._show_section("dashboard" if is_superadmin else "overview")
