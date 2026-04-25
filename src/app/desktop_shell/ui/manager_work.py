from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
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
from app.operations.services import OperationsService, OrderManagementItemRow


class StoreManagerWorkManagementScreen(QWidget):
    ROW_HEIGHT = 34
    CONTROL_HEIGHT = 26
    TABLE_HEADERS = (
        "Customer-item",
        "Item Status",
        "Due Date",
        "Priority",
        "Assignee",
        "Action",
    )
    STATUS_OPTIONS = ("INSTITCHING", "READY", "HOLD")

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
        self._rows: tuple[OrderManagementItemRow, ...] = ()
        self._apply_styles()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        top_card = QFrame()
        top_card.setObjectName("SummaryCard")
        top_layout = QGridLayout(top_card)
        top_layout.setContentsMargins(18, 12, 18, 12)
        top_layout.setHorizontalSpacing(16)
        top_layout.setVerticalSpacing(10)
        filter_card = self._filter_card()
        self.total_assigned_value = QLabel("0")
        self.total_institching_value = QLabel("0")
        self.total_hold_value = QLabel("0")
        top_layout.addWidget(filter_card, 0, 0)
        top_layout.addWidget(self._metric_block("TOTAL ASSIGNED", self.total_assigned_value), 0, 1)
        top_layout.addWidget(self._metric_block("TOTAL INSTITCHING", self.total_institching_value), 0, 2)
        top_layout.addWidget(self._metric_block("TOTAL HOLD", self.total_hold_value), 0, 3)
        top_layout.setColumnStretch(0, 2)
        top_layout.setColumnStretch(1, 1)
        top_layout.setColumnStretch(2, 1)
        top_layout.setColumnStretch(3, 1)

        table_card = QFrame()
        table_card.setObjectName("InnerCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(22, 22, 22, 22)
        table_layout.setSpacing(12)
        self.work_table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.work_table.setObjectName("DashboardTable")
        self.work_table.setHorizontalHeaderLabels(list(self.TABLE_HEADERS))
        self.work_table.setAlternatingRowColors(True)
        self.work_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.work_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.work_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.work_table.setShowGrid(False)
        self.work_table.verticalHeader().setVisible(False)
        self.work_table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)
        self.work_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.work_table.horizontalHeader().setStretchLastSection(False)
        self.work_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.work_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.work_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.work_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.work_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.work_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.work_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table_layout.addWidget(self.work_table, stretch=1)

        root.addWidget(top_card, stretch=15)
        root.addWidget(table_card, stretch=85)

        self.worker_filter.currentIndexChanged.connect(lambda _index=0: self.refresh_data())
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
        self._set_metrics(())
        self._set_worker_filter()
        self._set_table_rows(())

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
        self._rows = self._operations_service.list_work_management_items_for_store(
            store_id=self._store_context.store_id,
            worker_id=worker_id,
        )
        self._set_metrics(self._rows)
        self._set_table_rows(self._rows)

    def _set_metrics(self, rows: tuple[OrderManagementItemRow, ...]) -> None:
        self.total_assigned_value.setText(str(sum(1 for row in rows if row.item_status == "ASSIGNED")))
        self.total_institching_value.setText(str(sum(1 for row in rows if row.item_status == "INSTITCHING")))
        self.total_hold_value.setText(str(sum(1 for row in rows if row.item_status == "HOLD")))

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

    def _set_table_rows(self, rows: tuple[OrderManagementItemRow, ...]) -> None:
        self.work_table.clearSpans()
        self.work_table.clearContents()
        if not rows:
            self.work_table.setRowCount(1)
            self.work_table.setSpan(0, 0, 1, self.work_table.columnCount())
            empty_item = QTableWidgetItem("No assigned work available for the selected worker.")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.work_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.work_table.columnCount()):
                self.work_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.work_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (
                f"{row.customer_name}/{row.item_name}",
                self._format_date(row.due_date),
                row.priority,
                row.assigned_worker_name or "--",
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                table_column = column_index if column_index == 0 else column_index + 1
                self.work_table.setItem(row_index, table_column, item)

            status_combo = QComboBox()
            status_combo.setObjectName("InlineStatusSelect")
            status_combo.setFixedHeight(self.CONTROL_HEIGHT)
            status_values = (
                (row.item_status,)
                if row.item_status not in self.STATUS_OPTIONS
                else ()
            ) + self.STATUS_OPTIONS
            status_combo.addItems(status_values)
            status_combo.setCurrentText(row.item_status)
            self.work_table.setCellWidget(row_index, 1, status_combo)

            action_cell = QWidget()
            action_layout = QHBoxLayout(action_cell)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(0)
            action_button = QPushButton("Update")
            action_button.setObjectName("InlineActionButton")
            action_button.setFixedSize(58, self.CONTROL_HEIGHT)
            action_button.setEnabled(False)
            status_combo.currentTextChanged.connect(
                lambda value, button=action_button, original=row.item_status: button.setEnabled(
                    value != original
                )
            )
            action_button.clicked.connect(
                lambda _checked=False, order_item_id=row.order_item_id, combo=status_combo: (
                    self._update_item_status(order_item_id, combo.currentText())
                )
            )
            action_layout.addWidget(action_button, alignment=Qt.AlignmentFlag.AlignCenter)
            self.work_table.setCellWidget(row_index, 5, action_cell)

    def _update_item_status(self, order_item_id: int, status: str) -> None:
        if self._store_context is None:
            return
        try:
            self._operations_service.update_order_item_status_for_store(
                store_id=self._store_context.store_id,
                order_item_id=order_item_id,
                status=status,
            )
        except ValueError:
            return
        self.refresh_data()

    def _filter_card(self) -> QWidget:
        card = QWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel("Worker")
        label.setObjectName("FilterLabel")
        self.worker_filter = QComboBox()
        self.worker_filter.setObjectName("WorkerFilter")
        self.worker_filter.setFixedHeight(30)
        self.worker_filter.setMinimumWidth(220)
        layout.addWidget(label)
        layout.addWidget(self.worker_filter)
        layout.addStretch(1)
        return card

    def _metric_block(self, label: str, value_label: QLabel) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("MetricBlock")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(14, 2, 14, 2)
        layout.setSpacing(4)
        value_label.setObjectName("MetricValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return wrapper

    def _format_date(self, value: datetime | None) -> str:
        if value is None:
            return "--"
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QFrame#InnerCard {
                background-color: #f7f1ea;
                border: 1px solid #d8c6b4;
                border-radius: 8px;
            }
            QFrame#SummaryCard {
                background-color: transparent;
                border: none;
            }
            QWidget#MetricBlock {
                border-left: 1px solid #e3e8ef;
            }
            QLabel#MetricValue {
                color: #001f3f;
                font-size: 11pt;
                font-weight: 800;
            }
            QLabel#MetricLabel {
                color: #7a86a3;
                font-size: 7pt;
                font-weight: 800;
            }
            QLabel#MetricTitle, QLabel#FilterLabel {
                color: #001f3f;
                font-size: 9pt;
                font-weight: 700;
            }
            QComboBox#WorkerFilter {
                background-color: #ffffff;
                color: #001f3f;
                border: 1px solid #cdb8a4;
                border-radius: 6px;
                padding: 0 24px 0 10px;
                font-size: 9pt;
                min-height: 30px;
            }
            QComboBox#WorkerFilter:hover {
                border-color: #a1662b;
            }
            QComboBox#WorkerFilter::drop-down {
                width: 22px;
                border: none;
            }
            QComboBox#InlineStatusSelect {
                background-color: #ffffff;
                color: #001f3f;
                border: 1px solid #cdb8a4;
                border-radius: 5px;
                padding: 0 20px 0 8px;
                font-size: 8pt;
                min-height: 26px;
                max-height: 26px;
                min-width: 116px;
            }
            QComboBox#InlineStatusSelect::drop-down {
                width: 18px;
                border: none;
            }
            QTableWidget#DashboardTable {
                background-color: transparent;
                border: none;
                gridline-color: #eadfce;
                color: #001f3f;
                font-size: 8pt;
                alternate-background-color: #fbf8f4;
            }
            QTableWidget#DashboardTable::item {
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
            QPushButton#InlineActionButton {
                background-color: #8b5a2b;
                color: #ffffff;
                border: 1px solid #74481d;
                border-radius: 6px;
                font-size: 6.5pt;
                font-weight: 700;
                padding: 0;
                min-height: 26px;
                max-height: 26px;
            }
            QPushButton#InlineActionButton:hover {
                background-color: #6f451a;
            }
            QPushButton#InlineActionButton:disabled {
                background-color: #e7ded3;
                color: #8a7a68;
                border-color: #d8c6b4;
            }
            """
        )
