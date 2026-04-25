from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.admin.services import AdminUserManagementService, StoreDashboardContext, StoreStaffRow
from app.operations.services import (
    OperationsService,
    OrderManagementItemRow,
    WorkerAssignmentSummaryRow,
)


class WorkerAssignDialog(QDialog):
    def __init__(
        self,
        *,
        workers: tuple[StoreStaffRow, ...],
        current_worker_id: str = "",
        current_worker_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Assign Worker" if not current_worker_id else "Reassign Worker")
        self.setMinimumWidth(360)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #ffffff;
                color: #111827;
            }
            QLabel#SectionTitle {
                color: #111827;
                font-size: 16pt;
                font-weight: 800;
            }
            QLabel#SectionCopy {
                color: #475467;
                font-size: 10pt;
                font-weight: 500;
            }
            QComboBox {
                min-height: 38px;
                border: 1px solid #d0d5dd;
                border-radius: 8px;
                background-color: #ffffff;
                color: #111827;
                padding: 0 28px 0 12px;
                font-size: 10pt;
            }
            QPushButton#ActionButton {
                background-color: #a1662b;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 9px 24px;
                font-weight: 700;
            }
            QPushButton#SecondaryButton {
                background-color: #f3eadf;
                color: #001f3f;
                border: 1px solid #d8c6b4;
                border-radius: 8px;
                padding: 9px 24px;
                font-weight: 700;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Assign Worker" if not current_worker_id else "Reassign Worker")
        title.setObjectName("SectionTitle")
        current_assignee = QLabel(
            f"Current assignee: {current_worker_name.strip() or current_worker_id.strip()}"
            if current_worker_id
            else "Current assignee: Not assigned"
        )
        current_assignee.setObjectName("SectionCopy")
        self.worker_combo = QComboBox()
        self.worker_combo.setMinimumHeight(36)
        self.worker_combo.addItem("Select worker", "")
        for worker in workers:
            self.worker_combo.addItem(worker.full_name, worker.user_id)
        if current_worker_id:
            for index in range(self.worker_combo.count()):
                if self.worker_combo.itemData(index) == current_worker_id:
                    self.worker_combo.setCurrentIndex(index)
                    break

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.assign_button = QPushButton("Assign" if not current_worker_id else "Reassign")
        self.assign_button.setObjectName("ActionButton")
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.assign_button)

        root.addWidget(title)
        root.addWidget(current_assignee)
        root.addWidget(self.worker_combo)
        root.addLayout(actions)

        self.cancel_button.clicked.connect(self.reject)
        self.assign_button.clicked.connect(self.accept)

    def selected_worker(self) -> tuple[str, str] | None:
        worker_id = self.worker_combo.currentData()
        if not isinstance(worker_id, str) or not worker_id:
            return None
        return worker_id, self.worker_combo.currentText().strip()


class StoreManagerOrdersManagementScreen(QWidget):
    TABLE_HEADERS = (
        "Customer-item",
        "Item Status",
        "Due Date",
        "Priority",
        "Assignee",
        "Assign",
    )
    WORKER_HEADERS = ("Worker Name", "Assigned", "INSTITCHING")

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
        self._rows: tuple[OrderManagementItemRow, ...] = ()
        self._workers: tuple[StoreStaffRow, ...] = ()
        self._worker_assignments: tuple[WorkerAssignmentSummaryRow, ...] = ()
        self._apply_styles()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        metrics_row = QHBoxLayout()
        metrics_row.setContentsMargins(0, 0, 0, 0)
        metrics_row.setSpacing(12)
        self.new_hold_card_value = QLabel("0")
        self.worker_card_value = QLabel("0")
        self.assigned_today_card_value = QLabel("0")
        self.total_items_card_value = QLabel("0")
        metrics_row.addWidget(self._metric_card("NEW / HOLD Items", self.new_hold_card_value))
        metrics_row.addWidget(self._metric_card("Workers", self.worker_card_value))
        metrics_row.addWidget(self._metric_card("Today Assigned", self.assigned_today_card_value))
        metrics_row.addWidget(self._metric_card("Total Items", self.total_items_card_value))

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(14)

        left_panel = QFrame()
        left_panel.setObjectName("InnerCard")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(22, 22, 22, 22)
        left_layout.setSpacing(12)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(10)
        filter_label = QLabel("Due Date")
        filter_label.setObjectName("FilterLabel")
        self.due_date_filter = QComboBox()
        self.due_date_filter.setObjectName("DueDateFilter")
        self.due_date_filter.setFixedHeight(30)
        self.due_date_filter.setMinimumWidth(180)
        self.due_date_filter.addItem("All Due Dates", "")
        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.due_date_filter)
        filter_row.addStretch(1)

        self.orders_table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.orders_table.setObjectName("DashboardTable")
        self.orders_table.setHorizontalHeaderLabels(list(self.TABLE_HEADERS))
        self.orders_table.setAlternatingRowColors(True)
        self.orders_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.orders_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.orders_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.orders_table.setShowGrid(False)
        self.orders_table.verticalHeader().setVisible(False)
        self.orders_table.verticalHeader().setDefaultSectionSize(28)
        self.orders_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.orders_table.horizontalHeader().setStretchLastSection(False)
        self.orders_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.orders_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        left_layout.addLayout(filter_row)
        left_layout.addWidget(self.orders_table, stretch=1)

        right_panel = QFrame()
        right_panel.setObjectName("InnerCard")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 22, 14, 22)
        right_layout.setSpacing(10)
        right_title = QLabel("Workers")
        right_title.setObjectName("SectionTitle")
        self.worker_table = QTableWidget(0, len(self.WORKER_HEADERS))
        self.worker_table.setObjectName("WorkerTable")
        self.worker_table.setHorizontalHeaderLabels(list(self.WORKER_HEADERS))
        self.worker_table.setAlternatingRowColors(True)
        self.worker_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.worker_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.worker_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.worker_table.setShowGrid(False)
        self.worker_table.setWordWrap(False)
        self.worker_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.worker_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.worker_table.verticalHeader().setVisible(False)
        self.worker_table.verticalHeader().setDefaultSectionSize(28)
        self.worker_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.worker_table.horizontalHeader().setStretchLastSection(False)
        self.worker_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.worker_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.worker_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.worker_table.setColumnWidth(1, 74)
        self.worker_table.setColumnWidth(2, 88)
        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("StatusMessage")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.hide()
        right_layout.addWidget(right_title)
        right_layout.addWidget(self.worker_table, stretch=1)
        right_layout.addWidget(self.feedback_label)

        content_row.addWidget(left_panel, stretch=75)
        content_row.addWidget(right_panel, stretch=25)

        root.addLayout(metrics_row, stretch=15)
        root.addLayout(content_row, stretch=85)

        self.due_date_filter.currentIndexChanged.connect(
            lambda _index=0: self._apply_due_date_filter()
        )
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
        self._rows = ()
        self._workers = ()
        self._worker_assignments = ()
        self._set_metrics(0, 0, 0, 0)
        self._set_table_rows(())
        self._set_worker_assignment_rows()

    def refresh_data(self) -> None:
        if self._store_context is None:
            self.clear_context()
            return
        self._workers = self._user_management_service.list_store_workers(
            store_id=self._store_context.store_id
        )
        selected_due_date = self.due_date_filter.currentData()
        due_date = selected_due_date if isinstance(selected_due_date, datetime) else None
        self._rows = self._operations_service.list_order_management_items_for_store(
            store_id=self._store_context.store_id,
            due_date=due_date,
        )
        self._worker_assignments = self._operations_service.list_worker_assignment_summary_for_store(
            store_id=self._store_context.store_id
        )
        summary = self._operations_service.order_management_summary_for_store(
            store_id=self._store_context.store_id,
            worker_count=len(self._workers),
            due_date=due_date,
        )
        self._set_metrics(
            summary.new_hold_items,
            summary.worker_count,
            summary.todays_assigned,
            summary.total_items,
        )
        self._refresh_due_date_filter()
        self._set_worker_assignment_rows()
        self._set_table_rows(self._rows)

    def _refresh_due_date_filter(self) -> None:
        current_value = self.due_date_filter.currentData()
        all_rows = (
            self._operations_service.list_order_management_items_for_store(
                store_id=self._store_context.store_id
            )
            if self._store_context is not None
            else ()
        )
        due_dates = sorted({row.due_date.date() for row in all_rows if row.due_date is not None})
        self.due_date_filter.blockSignals(True)
        self.due_date_filter.clear()
        self.due_date_filter.addItem("All Due Dates", "")
        for due_date in due_dates:
            value = datetime(due_date.year, due_date.month, due_date.day, tzinfo=timezone.utc)
            self.due_date_filter.addItem(due_date.strftime("%Y-%m-%d"), value)
        for index in range(self.due_date_filter.count()):
            if self.due_date_filter.itemData(index) == current_value:
                self.due_date_filter.setCurrentIndex(index)
                break
        self.due_date_filter.blockSignals(False)

    def _apply_due_date_filter(self) -> None:
        self.refresh_data()

    def _set_metrics(
        self,
        new_hold_items: int,
        worker_count: int,
        todays_assigned: int,
        total_items: int,
    ) -> None:
        self.new_hold_card_value.setText(str(new_hold_items))
        self.worker_card_value.setText(str(worker_count))
        self.assigned_today_card_value.setText(str(todays_assigned))
        self.total_items_card_value.setText(str(total_items))

    def _set_worker_assignment_rows(self) -> None:
        assignment_lookup = {
            row.worker_id: row
            for row in self._worker_assignments
        }
        self.worker_table.clearSpans()
        self.worker_table.clearContents()
        if not self._workers:
            self.worker_table.setRowCount(1)
            self.worker_table.setSpan(0, 0, 1, self.worker_table.columnCount())
            empty_item = QTableWidgetItem("No workers available.")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.worker_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.worker_table.columnCount()):
                self.worker_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.worker_table.setRowCount(len(self._workers))
        for row_index, worker in enumerate(self._workers):
            assignment = assignment_lookup.get(worker.user_id)
            values = (
                worker.full_name,
                str(assignment.total_assigned_items if assignment is not None else 0),
                str(assignment.inprogress_items if assignment is not None else 0),
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.worker_table.setItem(row_index, column_index, item)

    def _set_table_rows(self, rows: tuple[OrderManagementItemRow, ...]) -> None:
        self.orders_table.clearSpans()
        self.orders_table.clearContents()
        if not rows:
            self.orders_table.setRowCount(1)
            self.orders_table.setSpan(0, 0, 1, self.orders_table.columnCount())
            empty_item = QTableWidgetItem("No order items available for the selected filter.")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.orders_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.orders_table.columnCount()):
                self.orders_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.orders_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            row_values = (
                f"{row.customer_name}/{row.item_name}",
                row.item_status,
                self._format_date(row.due_date),
                row.priority,
                row.assigned_worker_name or "--",
            )
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.orders_table.setItem(row_index, column_index, item)

            is_assigned = bool(row.assigned_worker_name) and row.item_status == "ASSIGNED"
            assign_button = QPushButton("Re-assign" if is_assigned else "Assign")
            assign_button.setObjectName("SmallActionButton")
            assign_button.setFixedSize(66 if is_assigned else 54, 20)
            assign_button.setToolTip(
                f"Assigned to {row.assigned_worker_name}"
                if row.assigned_worker_name
                else "Assign this item to a worker"
            )
            assign_button.clicked.connect(
                lambda _checked=False, order_item_id=row.order_item_id: self._open_assign_dialog(
                    order_item_id
                )
            )
            self.orders_table.setCellWidget(row_index, 5, assign_button)

    def _open_assign_dialog(self, order_item_id: int) -> None:
        if self._store_context is None:
            return
        if not self._workers:
            self._set_feedback("Create worker users before assigning order items.", tone="error")
            return
        current_row = next((row for row in self._rows if row.order_item_id == order_item_id), None)
        dialog = WorkerAssignDialog(
            workers=self._workers,
            current_worker_id=current_row.assigned_worker_id if current_row is not None else "",
            current_worker_name=current_row.assigned_worker_name if current_row is not None else "",
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_worker = dialog.selected_worker()
        if selected_worker is None:
            self._set_feedback("Select a worker before assigning.", tone="error")
            return
        worker_id, worker_name = selected_worker
        try:
            self._operations_service.assign_order_item_to_worker(
                store_id=self._store_context.store_id,
                order_item_id=order_item_id,
                worker_id=worker_id,
                worker_name=worker_name,
            )
        except ValueError as exc:
            self._set_feedback(str(exc), tone="error")
            return
        self._set_feedback("Order item assigned.", tone="success")
        self.refresh_data()

    def _set_feedback(self, message: str, *, tone: str) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(bool(message))
        self.feedback_label.setProperty("tone", tone)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.update()

    def _metric_card(self, title: str, value_label: QLabel) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        value_label.setObjectName("MetricValue")
        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")
        title_label.setWordWrap(True)
        layout.addWidget(value_label)
        layout.addWidget(title_label)
        return card

    def _format_date(self, value: datetime | None) -> str:
        if value is None:
            return "--"
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QFrame#MetricCard, QFrame#InnerCard {
                background-color: #f7f1ea;
                border: 1px solid #d8c6b4;
                border-radius: 8px;
            }
            QLabel#MetricValue {
                color: #001f3f;
                font-size: 18pt;
                font-weight: 800;
            }
            QLabel#MetricTitle, QLabel#FilterLabel {
                color: #001f3f;
                font-size: 9pt;
                font-weight: 700;
            }
            QLabel#FilterLabel {
                padding: 0;
            }
            QComboBox#DueDateFilter {
                background-color: #ffffff;
                color: #001f3f;
                border: 1px solid #cdb8a4;
                border-radius: 6px;
                padding: 0 24px 0 10px;
                font-size: 9pt;
                min-height: 30px;
            }
            QComboBox#DueDateFilter:hover {
                border-color: #a1662b;
            }
            QComboBox#DueDateFilter::drop-down {
                width: 22px;
                border: none;
            }
            QLabel#SectionTitle {
                color: #001f3f;
                font-size: 14pt;
                font-weight: 800;
            }
            QLabel#SectionCopy {
                color: #344054;
                font-size: 10pt;
            }
            QTableWidget#DashboardTable, QTableWidget#WorkerTable {
                background-color: transparent;
                border: none;
                gridline-color: #eadfce;
                color: #001f3f;
                font-size: 8pt;
                alternate-background-color: #fbf8f4;
            }
            QTableWidget#WorkerTable {
                font-size: 7.5pt;
            }
            QTableWidget#DashboardTable::item, QTableWidget#WorkerTable::item {
                padding-left: 8px;
                border-bottom: 1px solid #eadfce;
            }
            QHeaderView::section {
                background-color: #e8dccd;
                color: #111827;
                border: none;
                border-bottom: 1px solid #d8c6b4;
                padding: 6px 8px;
                font-size: 10pt;
                font-weight: 700;
            }
            QTableWidget#WorkerTable QHeaderView::section {
                padding: 5px 6px;
                font-size: 7.5pt;
            }
            QPushButton#SmallActionButton {
                background-color: #8b5a2b;
                color: #ffffff;
                border: 1px solid #74481d;
                border-radius: 10px;
                font-size: 7pt;
                font-weight: 700;
                padding: 0 8px;
            }
            QPushButton#SmallActionButton:hover {
                background-color: #6f451a;
            }
            QPushButton#SmallActionButton:pressed {
                background-color: #55330f;
            }
            QPushButton#ActionButton {
                background-color: #a1662b;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
            }
            QPushButton#SecondaryButton {
                background-color: #f0e8dd;
                color: #001f3f;
                border: 1px solid #d8c6b4;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
            }
            QLabel#StatusMessage {
                padding: 8px 10px;
                border-radius: 8px;
                font-size: 9pt;
                font-weight: 700;
            }
            QLabel#StatusMessage[tone="error"] {
                background-color: #fef2f2;
                color: #b42318;
                border: 1px solid #fecaca;
            }
            QLabel#StatusMessage[tone="success"] {
                background-color: #ecfdf3;
                color: #027a48;
                border: 1px solid #abefc6;
            }
            """
        )
