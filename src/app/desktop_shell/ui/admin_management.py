from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)


@dataclass(slots=True)
class UserRecord:
    user_id: str
    username: str
    full_name: str
    status: str
    department: str


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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._filter_column = filter_column

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        subheading = QLabel(subtitle)
        subheading.setStyleSheet("color: #555;")

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Search"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search all columns...")
        controls.addWidget(self.search_input, stretch=2)

        controls.addWidget(QLabel(filter_label))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", *filter_options])
        controls.addWidget(self.filter_combo)

        controls.addStretch(1)

        self.model = _AdminTableModel(headers=headers, rows=rows, parent=self)
        self.proxy_model = AdminFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.status_label = QLabel(self._status_text())
        self.status_label.setStyleSheet("color: #555;")

        root.addWidget(heading)
        root.addWidget(subheading)
        root.addLayout(controls)
        root.addWidget(self.table)
        root.addWidget(self.status_label)

        self.search_input.textChanged.connect(self._on_search_changed)
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        self.proxy_model.rowsInserted.connect(lambda *_: self._refresh_status())
        self.proxy_model.rowsRemoved.connect(lambda *_: self._refresh_status())
        self.proxy_model.modelReset.connect(self._refresh_status)

    def _status_text(self) -> str:
        return f"Showing {self.proxy_model.rowCount()} of {self.model.rowCount()} records"

    def _refresh_status(self) -> None:
        self.status_label.setText(self._status_text())

    def _on_search_changed(self, text: str) -> None:
        self.proxy_model.setFilterFixedString(text)
        self._refresh_status()

    def _on_filter_changed(self, value: str) -> None:
        self.proxy_model.set_exact_filter(column=self._filter_column, value=value)
        self._refresh_status()


class AssignmentDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        source_label: str,
        target_label: str,
        source_items: list[str],
        target_items: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(760, 420)

        root = QVBoxLayout(self)

        labels = QFormLayout()
        labels.addRow("Source", QLabel(source_label))
        labels.addRow("Assigned", QLabel(target_label))
        root.addLayout(labels)

        splitter = QSplitter()
        self.available_list = QListWidget()
        self.available_list.addItems(source_items)

        self.assigned_list = QListWidget()
        self.assigned_list.addItems(target_items)

        transfer_controls = QWidget()
        transfer_layout = QVBoxLayout(transfer_controls)
        transfer_layout.addStretch(1)

        self.assign_button = QPushButton("Assign →")
        self.unassign_button = QPushButton("← Remove")
        transfer_layout.addWidget(self.assign_button)
        transfer_layout.addWidget(self.unassign_button)
        transfer_layout.addStretch(1)

        splitter.addWidget(self.available_list)
        splitter.addWidget(transfer_controls)
        splitter.addWidget(self.assigned_list)
        splitter.setSizes([280, 120, 280])

        root.addWidget(splitter)

        actions = QHBoxLayout()
        actions.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        root.addLayout(actions)

        self.assign_button.clicked.connect(self._assign_selected)
        self.unassign_button.clicked.connect(self._unassign_selected)

    def _assign_selected(self) -> None:
        current = self.available_list.currentItem()
        if current is None:
            return
        self._move_item(current, self.available_list, self.assigned_list)

    def _unassign_selected(self) -> None:
        current = self.assigned_list.currentItem()
        if current is None:
            return
        self._move_item(current, self.assigned_list, self.available_list)

    def _move_item(self, item: QListWidgetItem, origin: QListWidget, destination: QListWidget) -> None:
        text = item.text()
        origin.takeItem(origin.row(item))
        destination.addItem(text)


class UserRoleAssignmentDialog(AssignmentDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Assign Roles to User",
            source_label="Available roles",
            target_label="User roles",
            source_items=["Billing Analyst", "Support Agent", "Audit Reader", "Security Officer"],
            target_items=["System Admin"],
            parent=parent,
        )


class RolePermissionAssignmentDialog(AssignmentDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Assign Permissions to Role",
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
            parent=parent,
        )


class AccessControlWorkspace(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Access Control Management")
        self.resize(980, 640)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Manage users, roles, and permissions with searchable and sortable grids."
        )
        intro.setStyleSheet("color: #555;")

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_user_screen(), "Users")
        self.tabs.addTab(self._build_role_screen(), "Roles")
        self.tabs.addTab(self._build_permission_screen(), "Permissions")

        actions = QHBoxLayout()
        self.user_assignment_button = QPushButton("Assign Roles to Selected User")
        self.role_assignment_button = QPushButton("Assign Permissions to Selected Role")
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        actions.addWidget(self.user_assignment_button)
        actions.addWidget(self.role_assignment_button)
        actions.addStretch(1)
        actions.addWidget(close_button)

        root.addWidget(intro)
        root.addWidget(self.tabs)
        root.addLayout(actions)

        self.user_assignment_button.clicked.connect(self._open_user_assignment)
        self.role_assignment_button.clicked.connect(self._open_role_assignment)

    def _build_user_screen(self) -> QWidget:
        users = [
            UserRecord("U-1001", "asmith", "Alice Smith", "Active", "Finance"),
            UserRecord("U-1002", "bjones", "Brandon Jones", "Active", "Operations"),
            UserRecord("U-1003", "cmiller", "Candice Miller", "Suspended", "Security"),
            UserRecord("U-1004", "dnguyen", "Diana Nguyen", "Invited", "HR"),
            UserRecord("U-1005", "egarcia", "Ethan Garcia", "Active", "Engineering"),
        ]
        rows = [(u.user_id, u.username, u.full_name, u.status, u.department) for u in users]
        return ManagementGridScreen(
            title="User Management",
            subtitle="Manage directory users, account status, and department ownership.",
            headers=["User ID", "Username", "Name", "Status", "Department"],
            rows=rows,
            filter_label="Status",
            filter_column=3,
            filter_options=["Active", "Invited", "Suspended"],
        )

    def _build_role_screen(self) -> QWidget:
        roles = [
            RoleRecord("ROLE_ADMIN", "System Admin", "Global", 5),
            RoleRecord("ROLE_BILLING", "Billing Analyst", "Finance", 12),
            RoleRecord("ROLE_SUPPORT", "Support Agent", "Operations", 21),
            RoleRecord("ROLE_AUDIT", "Audit Reader", "Global", 8),
        ]
        rows = [(r.role_key, r.role_name, r.scope, str(r.assignments)) for r in roles]
        return ManagementGridScreen(
            title="Role Management",
            subtitle="Control role definitions and monitor assignment volumes.",
            headers=["Role Key", "Role Name", "Scope", "Assignments"],
            rows=rows,
            filter_label="Scope",
            filter_column=2,
            filter_options=["Global", "Finance", "Operations"],
        )

    def _build_permission_screen(self) -> QWidget:
        permissions = [
            PermissionRecord("user:view", "Users", "Read", "Low"),
            PermissionRecord("user:edit", "Users", "Write", "Medium"),
            PermissionRecord("role:assign", "Roles", "Write", "High"),
            PermissionRecord("permission:view", "Permissions", "Read", "Low"),
            PermissionRecord("billing:refund", "Billing", "Write", "Critical"),
        ]
        rows = [
            (p.permission_key, p.module, p.action, p.risk_level)
            for p in permissions
        ]
        return ManagementGridScreen(
            title="Permission Management",
            subtitle="Maintain fine-grained capabilities with explicit risk levels.",
            headers=["Permission", "Module", "Action", "Risk"],
            rows=rows,
            filter_label="Risk",
            filter_column=3,
            filter_options=["Low", "Medium", "High", "Critical"],
        )

    def _open_user_assignment(self) -> None:
        dialog = UserRoleAssignmentDialog(self)
        dialog.exec()

    def _open_role_assignment(self) -> None:
        dialog = RolePermissionAssignmentDialog(self)
        dialog.exec()
