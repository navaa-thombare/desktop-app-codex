from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.admin.services import AdminUserManagementService, StoreDashboardContext
from app.operations.services import (
    CustomerSummaryRow,
    CustomerOrderCreateInput,
    ItemRow,
    OrderQueueRow,
    OperationsService,
    OrderItemCreateInput,
)


@dataclass(frozen=True)
class ManagerCustomerSummary:
    customer_id: str
    full_name: str
    mobile: str
    email: str
    last_order_on: datetime | None
    balance_amount: Decimal


@dataclass(frozen=True)
class ManagerOrderQueueRow:
    customer_name: str
    order_date: datetime
    due_date: datetime | None
    priority: str
    item_name: str
    status: str


@dataclass(frozen=True)
class ManagerOrderItemDraft:
    item_id: str
    item_name: str
    quantity: int
    measurements: str
    rate: Decimal
    status: str
    updated_on: datetime
    updated_by: str

    @property
    def line_amount(self) -> Decimal:
        return (self.rate * Decimal(self.quantity)).quantize(Decimal("0.01"))


def _apply_compact_table_style(
    table: QTableWidget,
    *,
    row_height: int,
    embedded: bool = False,
) -> None:
    table_font = table.font()
    table_font.setPointSize(10)
    table.setFont(table_font)
    header_font = table.horizontalHeader().font()
    header_font.setPointSize(10)
    header_font.setBold(True)
    table.horizontalHeader().setFont(header_font)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideNone)
    table.verticalHeader().setDefaultSectionSize(row_height)
    if embedded:
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.setContentsMargins(0, 0, 0, 0)
    else:
        table.setFrameShape(QFrame.Shape.StyledPanel)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class CustomerOrderEntryDialog(QDialog):
    ITEM_HEADERS = (
        "Item",
        "Qty",
        "Measurements",
        "Amount (INR)",
    )

    def __init__(
        self,
        *,
        item_rows: tuple[ItemRow, ...],
        created_by_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item_lookup = {row.item_id: row for row in item_rows}
        self._created_by_name = created_by_name.strip() or "Current manager"
        self._draft_items: list[ManagerOrderItemDraft] = []
        self._order_created_on = datetime.now(tz=timezone.utc)
        self._feedback_clear_timer = QTimer(self)
        self._feedback_clear_timer.setSingleShot(True)
        self._feedback_clear_timer.timeout.connect(
            lambda: self.set_feedback("", tone="success")
        )
        self.setModal(True)
        self.setWindowTitle("Add New Customer")
        self.setMinimumSize(960, 620)
        self.resize(1040, 660)
        self._apply_dialog_styles()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(18)
        icon = QLabel("+")
        icon.setObjectName("DialogHeaderIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(48, 48)
        header_copy = QVBoxLayout()
        header_copy.setSpacing(4)
        title = QLabel("Add New Customer")
        title.setObjectName("DialogTitle")
        copy = QLabel("Enter customer details, order metadata and items")
        copy.setObjectName("DialogSubtitle")
        copy.setWordWrap(True)
        header_copy.addWidget(title)
        header_copy.addWidget(copy)
        header.addWidget(icon)
        header.addLayout(header_copy, stretch=1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("DialogSecondaryButton")
        self.save_button = QPushButton("Save Customer")
        self.save_button.setObjectName("DialogPrimaryButton")
        self.close_button = QPushButton("X")
        self.close_button.setObjectName("DialogCloseButton")
        self.close_button.setFixedSize(32, 32)
        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)
        header.addLayout(actions)
        header.addWidget(self.close_button)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("StatusMessage")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.hide()

        top_sections = QGridLayout()
        top_sections.setContentsMargins(0, 0, 0, 0)
        top_sections.setHorizontalSpacing(12)
        top_sections.setVerticalSpacing(12)
        top_sections.setColumnStretch(0, 3)
        top_sections.setColumnStretch(1, 2)

        customer_card = self._build_dialog_card()
        customer_layout = QVBoxLayout(customer_card)
        customer_layout.setContentsMargins(16, 14, 16, 16)
        customer_layout.setSpacing(10)
        customer_title = self._section_heading("+", "Customer Details")
        customer_form = QGridLayout()
        customer_form.setHorizontalSpacing(12)
        customer_form.setVerticalSpacing(10)
        customer_form.setColumnStretch(0, 1)
        customer_form.setColumnStretch(1, 1)

        self.full_name_input = QLineEdit()
        self.mobile_input = QLineEdit()
        self.whatsapp_checkbox = QCheckBox("WhatsApp")
        self.whatsapp_checkbox.setChecked(False)
        self.address_input = QPlainTextEdit()
        self.address_input.setFixedHeight(72)
        self.full_name_input.setPlaceholderText("Enter full name")
        self.mobile_input.setPlaceholderText("Contact number")
        self.address_input.setPlaceholderText("Enter address")
        self._dialog_control(self.full_name_input, self.mobile_input)

        contact_row = QHBoxLayout()
        contact_row.setContentsMargins(0, 0, 0, 0)
        contact_row.setSpacing(10)
        contact_row.addWidget(self.mobile_input, stretch=1)
        contact_row.addWidget(self.whatsapp_checkbox)
        contact_widget = QWidget()
        contact_widget.setLayout(contact_row)

        customer_form.addWidget(self._field_block("Full Name *", self.full_name_input), 0, 0)
        customer_form.addWidget(self._field_block("Contact Number *", contact_widget), 0, 1)
        customer_form.addWidget(self._field_block("Address", self.address_input), 1, 0, 1, 2)
        customer_layout.addWidget(customer_title)
        customer_layout.addLayout(customer_form)

        metadata_card = self._build_dialog_card()
        metadata_layout = QVBoxLayout(metadata_card)
        metadata_layout.setContentsMargins(16, 14, 16, 16)
        metadata_layout.setSpacing(10)
        metadata_title = self._section_heading("#", "Order Metadata")
        metadata_form = QGridLayout()
        metadata_form.setHorizontalSpacing(12)
        metadata_form.setVerticalSpacing(10)
        metadata_form.setColumnStretch(0, 1)
        metadata_form.setColumnStretch(1, 1)

        self.due_date_input = QDateEdit()
        self.due_date_input.setCalendarPopup(True)
        self.due_date_input.setDisplayFormat("MMM dd, yyyy")
        self.due_date_input.setDate(QDate.currentDate().addDays(7))
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(("High", "Medium", "Low"))
        self.priority_combo.setCurrentText("Medium")
        self._dialog_control(
            self.due_date_input,
            self.priority_combo,
        )

        metadata_form.addWidget(self._field_block("Due Date *", self.due_date_input), 0, 0)
        metadata_form.addWidget(self._field_block("Priority *", self.priority_combo), 0, 1)
        metadata_layout.addWidget(metadata_title)
        metadata_layout.addLayout(metadata_form)

        top_sections.addWidget(customer_card, 0, 0)
        top_sections.addWidget(metadata_card, 0, 1)

        items_card = self._build_dialog_card()
        items_layout = QVBoxLayout(items_card)
        items_layout.setContentsMargins(18, 18, 18, 18)
        items_layout.setSpacing(12)
        items_header = QHBoxLayout()
        items_header.setContentsMargins(0, 0, 0, 0)
        items_header.setSpacing(16)
        items_title = self._section_heading("*", "Order Items")
        items_header.addWidget(items_title, stretch=1)

        entry_row = QHBoxLayout()
        entry_row.setContentsMargins(0, 0, 0, 0)
        entry_row.setSpacing(12)

        self.item_combo = QComboBox()
        self.item_combo.addItem("Search or select item", "")
        for item_row in item_rows:
            self.item_combo.addItem(item_row.item_name, item_row.item_id)
        self.quantity_input = QSpinBox()
        self.quantity_input.setMinimum(1)
        self.quantity_input.setMaximum(999)
        self.measurements_input = QLineEdit()
        self.measurements_input.setPlaceholderText("Enter measurements")
        self.add_item_button = QPushButton("Add Item")
        self.add_item_button.setObjectName("DialogPrimaryButton")
        self.reset_item_button = QPushButton("Reset")
        self.reset_item_button.setObjectName("DialogSecondaryButton")
        self.remove_item_button = QPushButton("Remove Selected")
        self.remove_item_button.setObjectName("DialogSecondaryButton")
        self.remove_item_button.hide()
        self._dialog_control(
            self.item_combo,
            self.quantity_input,
            self.measurements_input,
        )

        item_quantity_panel = QWidget()
        item_quantity_layout = QHBoxLayout(item_quantity_panel)
        item_quantity_layout.setContentsMargins(0, 0, 0, 0)
        item_quantity_layout.setSpacing(10)
        item_quantity_layout.addWidget(
            self._field_block("Item *", self.item_combo),
            stretch=2,
        )
        item_quantity_layout.addWidget(
            self._field_block("Quantity *", self.quantity_input),
            stretch=1,
        )
        entry_row.addWidget(item_quantity_panel, stretch=30)
        entry_row.addWidget(
            self._field_block("Measurements", self.measurements_input),
            stretch=40,
        )
        entry_row.addWidget(
            self._button_block("", self.reset_item_button),
            stretch=15,
        )
        entry_row.addWidget(
            self._button_block("", self.add_item_button),
            stretch=15,
        )

        self.items_table = QTableWidget(0, len(self.ITEM_HEADERS))
        self.items_table.setObjectName("DialogItemsTable")
        self.items_table.setHorizontalHeaderLabels(list(self.ITEM_HEADERS))
        self.items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.setShowGrid(False)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.verticalHeader().setDefaultSectionSize(30)
        header_height = 30
        visible_rows_height = self.items_table.verticalHeader().defaultSectionSize() * 4
        table_height = header_height + visible_rows_height + (self.items_table.frameWidth() * 2)
        self.items_table.setMinimumHeight(table_height)
        self.items_table.setMaximumHeight(table_height)
        self.items_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.items_table.horizontalHeader().setStretchLastSection(False)
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        _apply_compact_table_style(self.items_table, row_height=30)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(14)
        self.bill_amount_input = self._summary_value("0.00")
        self.paid_amount_input = QLineEdit("0.00")
        self.paid_amount_input.setObjectName("SummaryAmountInput")
        self.balance_amount_input = self._summary_value("0.00")
        self._dialog_control(self.paid_amount_input)
        summary_row.addWidget(self._summary_block("Bill Amount (INR)", self.bill_amount_input))
        summary_row.addWidget(self._summary_block("Paid Amount (INR)", self.paid_amount_input))
        summary_row.addWidget(self._summary_block("Balance (INR)", self.balance_amount_input))
        items_header.addLayout(summary_row)

        items_layout.addLayout(items_header)
        items_layout.addLayout(entry_row)
        items_layout.addWidget(self.items_table)

        root.addLayout(header)
        root.addWidget(self.feedback_label)
        root.addLayout(top_sections)
        root.addWidget(items_card)
        root.addStretch(1)

        self.cancel_button.clicked.connect(self.reject)
        self.close_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._attempt_accept)
        self.add_item_button.clicked.connect(self._add_item)
        self.reset_item_button.clicked.connect(self._reset_item_entry)
        self.remove_item_button.clicked.connect(self._remove_selected_item)
        self.item_combo.currentIndexChanged.connect(self._refresh_item_defaults)
        self.quantity_input.valueChanged.connect(self._refresh_item_defaults)
        self.paid_amount_input.textChanged.connect(self._update_bill_amount)
        self._refresh_item_defaults()
        self._refresh_items_table()

    def payload(self) -> dict[str, object]:
        due_date = self.due_date_input.date().toPython()
        due_on = datetime(due_date.year, due_date.month, due_date.day, tzinfo=timezone.utc)
        items = tuple(
            OrderItemCreateInput(
                item_id=draft.item_id,
                item_name=draft.item_name,
                quantity=draft.quantity,
                measurements=draft.measurements,
                rate=draft.rate,
                status=draft.status,
                updated_on=draft.updated_on,
                updated_by=draft.updated_by,
            )
            for draft in self._draft_items
        )
        return {
            "full_name": self.full_name_input.text().strip(),
            "mobile": self.mobile_input.text().strip(),
            "address": self.address_input.toPlainText().strip(),
            "whatsapp_enabled": self.whatsapp_checkbox.isChecked(),
            "created_on": self._order_created_on,
            "created_by": self._created_by_name,
            "due_on": due_on,
            "priority": self.priority_combo.currentText().strip(),
            "order_status": "NEW",
            "bill_amount": self._bill_amount(),
            "paid_amount": self._parse_paid_amount(self.paid_amount_input.text()),
            "items": items,
        }

    def set_feedback(self, message: str, *, tone: str) -> None:
        self._feedback_clear_timer.stop()
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(bool(message))
        self.feedback_label.setProperty("tone", tone)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.update()
        if message:
            self._feedback_clear_timer.start(30_000)

    def _attempt_accept(self) -> None:
        if not self.full_name_input.text().strip():
            self.set_feedback("Full name is required.", tone="error")
            return
        if not self.mobile_input.text().strip():
            self.set_feedback("Contact number is required.", tone="error")
            return
        if not self.address_input.toPlainText().strip():
            self.set_feedback("Address is required.", tone="error")
            return
        if not self._draft_items:
            self.set_feedback("Add at least one order item before saving.", tone="error")
            return
        try:
            paid_amount = self._parse_paid_amount(self.paid_amount_input.text())
        except ValueError as exc:
            self.set_feedback(str(exc), tone="error")
            return
        if paid_amount > self._bill_amount():
            self.set_feedback("Paid amount cannot be greater than bill amount.", tone="error")
            return
        self.accept()

    def _add_item(self) -> None:
        item_row = self._selected_item_row()
        if item_row is None:
            self.set_feedback("Select an item before adding it.", tone="error")
            return
        updated_on = datetime.now(tz=timezone.utc)
        self._draft_items.append(
            ManagerOrderItemDraft(
                item_id=item_row.item_id,
                item_name=item_row.item_name,
                quantity=self.quantity_input.value(),
                measurements=self.measurements_input.text().strip(),
                rate=item_row.cost,
                status="NEW",
                updated_on=updated_on,
                updated_by=self._created_by_name,
            )
        )
        self._reset_item_entry()
        self._update_bill_amount()
        self._refresh_items_table()
        self.set_feedback("", tone="success")

    def _reset_item_entry(self) -> None:
        self.quantity_input.setValue(1)
        self.item_combo.setCurrentIndex(0)
        self.measurements_input.clear()
        self._refresh_item_defaults()

    def _remove_selected_item(self) -> None:
        current_row = self.items_table.currentRow()
        if current_row < 0 or current_row >= len(self._draft_items):
            self.set_feedback("Select an item row before removing it.", tone="error")
            return
        del self._draft_items[current_row]
        self._update_bill_amount()
        self._refresh_items_table()
        self.set_feedback("", tone="success")

    def _selected_item_row(self) -> ItemRow | None:
        item_id = self.item_combo.currentData()
        if not isinstance(item_id, str) or not item_id:
            return None
        return self._item_lookup.get(item_id)

    def _refresh_item_defaults(self) -> None:
        selected_item = self._selected_item_row()
        self.add_item_button.setEnabled(selected_item is not None)

    def _refresh_items_table(self) -> None:
        self.items_table.clearSpans()
        self.items_table.clearContents()
        if not self._draft_items:
            self.items_table.setRowCount(1)
            self.items_table.setSpan(0, 0, 1, self.items_table.columnCount())
            empty_item = QTableWidgetItem("No order items added yet.")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.items_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.items_table.columnCount()):
                self.items_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.items_table.setRowCount(len(self._draft_items))
        for row_index, draft in enumerate(self._draft_items):
            row_values = (
                draft.item_name,
                str(draft.quantity),
                draft.measurements or "--",
                self._format_currency(draft.line_amount),
            )
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if column_index in {1, 3}
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                self.items_table.setItem(row_index, column_index, item)

    def _bill_amount(self) -> Decimal:
        total = Decimal("0.00")
        for draft in self._draft_items:
            total += draft.line_amount
        return total.quantize(Decimal("0.01"))

    def _update_bill_amount(self) -> None:
        bill_amount = self._bill_amount()
        self.bill_amount_input.setText(f"{bill_amount:,.2f}")
        try:
            paid_amount = self._parse_paid_amount(self.paid_amount_input.text())
        except ValueError:
            paid_amount = Decimal("0.00")
        balance_amount = max(Decimal("0.00"), bill_amount - paid_amount)
        self.balance_amount_input.setText(f"{balance_amount.quantize(Decimal('0.01')):,.2f}")

    def _parse_paid_amount(self, value: str) -> Decimal:
        normalized_value = (value.strip() or "0.00").replace(",", "")
        try:
            parsed = Decimal(normalized_value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Enter a valid paid amount.") from exc
        if parsed < Decimal("0.00"):
            raise ValueError("Paid amount cannot be negative.")
        return parsed.quantize(Decimal("0.01"))

    def _compact(self, *widgets: QWidget) -> None:
        for widget in widgets:
            if hasattr(widget, "setMinimumHeight"):
                widget.setMinimumHeight(34)

    def _dialog_control(self, *widgets: QWidget) -> None:
        for widget in widgets:
            if hasattr(widget, "setMinimumHeight"):
                widget.setMinimumHeight(40)

    def _readonly_input(self, value: str) -> QLineEdit:
        widget = QLineEdit(value)
        widget.setReadOnly(True)
        widget.setMinimumHeight(40)
        return widget

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setMinimumWidth(112)
        return label

    def _build_dialog_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("DialogCard")
        return card

    def _section_heading(self, icon_text: str, title: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        icon = QLabel(icon_text)
        icon.setObjectName("DialogSectionIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(30, 30)
        label = QLabel(title)
        label.setObjectName("DialogSectionTitle")
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch(1)
        return widget

    def _summary_value(self, value: str) -> QLineEdit:
        widget = QLineEdit(value)
        widget.setReadOnly(True)
        widget.setObjectName("SummaryAmountInput")
        return widget

    def _summary_block(self, title: str, value_widget: QWidget) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        label = QLabel(title)
        label.setObjectName("SummaryLabel")
        layout.addWidget(label)
        layout.addWidget(value_widget)
        return block

    def _field_block(self, title: str, widget: QWidget) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = self._label(title)
        label.setMinimumWidth(0)
        layout.addWidget(label)
        layout.addWidget(widget)
        return block

    def _button_block(self, title: str, button: QPushButton) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(title)
        label.setObjectName("FormLabel")
        label.setFixedHeight(18)
        layout.addWidget(label)
        layout.addWidget(button)
        return block

    def _status_value(self, value: str) -> str:
        return value.strip().replace(" ", "").upper()

    def _format_currency(self, value: Decimal) -> str:
        return f"INR {value.quantize(Decimal('0.01')):,.2f}"

    def _apply_dialog_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #ffffff;
                color: #111827;
            }
            QLabel#DialogHeaderIcon, QLabel#DialogSectionIcon {
                background-color: #f1efff;
                border-radius: 15px;
                color: #4f46e5;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#DialogHeaderIcon {
                border-radius: 24px;
                font-size: 24px;
            }
            QLabel#DialogTitle {
                color: #111827;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#DialogSubtitle, QLabel#SummaryLabel {
                color: #8a94ad;
                font-size: 9pt;
                font-weight: 700;
            }
            QLabel#DialogSectionTitle {
                color: #111827;
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#FormLabel {
                color: #1f2937;
                font-size: 13px;
                font-weight: 600;
                padding: 0;
            }
            QFrame#DialogCard {
                background-color: #ffffff;
                border: 1px solid #e5e7ef;
                border-radius: 10px;
            }
            QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit {
                min-height: 38px;
                border: 1px solid #dfe3ec;
                border-radius: 8px;
                background-color: #ffffff;
                color: #30384d;
                padding: 0 10px;
                selection-background-color: #4f46e5;
                font-size: 13px;
            }
            QPlainTextEdit {
                padding: 8px 10px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {
                border: 1px solid #4f46e5;
            }
            QCheckBox {
                color: #30384d;
                font-size: 14px;
                spacing: 8px;
            }
            QPushButton#DialogPrimaryButton {
                min-height: 42px;
                border: none;
                border-radius: 8px;
                background-color: #5147e8;
                color: #ffffff;
                font-weight: 700;
                padding: 0 22px;
            }
            QPushButton#DialogPrimaryButton:hover {
                background-color: #463dd4;
            }
            QPushButton#DialogPrimaryButton:disabled {
                background-color: #b8b5f4;
            }
            QPushButton#DialogSecondaryButton {
                min-height: 42px;
                border: 1px solid #dfe3ec;
                border-radius: 8px;
                background-color: #ffffff;
                color: #30384d;
                font-weight: 700;
                padding: 0 18px;
            }
            QPushButton#DialogSecondaryButton:hover {
                background-color: #f8fafc;
            }
            QPushButton#DialogCloseButton {
                border: none;
                background-color: transparent;
                color: #30384d;
                font-size: 18px;
                font-weight: 500;
            }
            QTableWidget#DialogItemsTable {
                background-color: #ffffff;
                alternate-background-color: #fbfcff;
                border: 1px solid #e7eaf3;
                border-radius: 8px;
                color: #111827;
                gridline-color: #eef1f7;
                outline: none;
            }
            QTableWidget#DialogItemsTable::item {
                padding: 2px;
                border-bottom: 1px solid #eef1f7;
            }
            QTableWidget#DialogItemsTable QHeaderView::section {
                background-color: #f1f0ff;
                color: #111827;
                border: none;
                border-bottom: 1px solid #e5e7ef;
                padding: 3px;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit#SummaryAmountInput {
                min-width: 92px;
                min-height: 20px;
                border: none;
                background-color: transparent;
                color: #111827;
                font-size: 8pt;
                font-weight: 300;
                padding: 0;
            }
            QLineEdit#SummaryAmountInput:focus {
                border: none;
            }
            QLabel#StatusMessage {
                padding: 10px 12px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
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


class StoreManagerCustomerDashboardScreen(QWidget):
    TABLE_HEADERS = ("Name", "Phone", "Last Order", "Balance")
    FUTURE_HEADERS = ("Customer Name", "Order Date", "Due Date", "Priority", "Item Name")
    CUSTOMER_PAGE_SIZE = 10
    CUSTOMER_VISIBLE_ROWS = CUSTOMER_PAGE_SIZE
    FUTURE_VISIBLE_ROWS = 15

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
        self._all_rows: tuple[ManagerCustomerSummary, ...] = ()
        self._cached_rows_by_id: dict[str, ManagerCustomerSummary] = {}
        self._visible_customer_rows: tuple[ManagerCustomerSummary, ...] = ()
        self._current_page = 0
        self._total_customer_rows = 0
        self._active_query = ""
        self._database_search_active = False
        self._order_queue_rows: tuple[ManagerOrderQueueRow, ...] = ()
        self._feedback_clear_timer = QTimer(self)
        self._feedback_clear_timer.setSingleShot(True)
        self._feedback_clear_timer.timeout.connect(
            lambda: self._set_feedback("", tone="success")
        )
        self._apply_styles()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(18)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnMinimumWidth(0, 0)
        layout.setColumnMinimumWidth(1, 0)

        future_card = QFrame()
        future_card.setObjectName("InnerCard")
        future_card.setProperty("managerPanel", True)
        future_layout = QVBoxLayout(future_card)
        future_layout.setContentsMargins(28, 28, 28, 28)
        future_layout.setSpacing(14)
        future_title = QLabel("Future Use")
        future_title.setObjectName("SectionTitle")
        future_copy = QLabel("Store orders are listed here with NEW status rows shown first.")
        future_copy.setObjectName("SectionCopy")
        future_copy.setWordWrap(True)
        future_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        future_layout.addWidget(future_title)
        future_layout.addWidget(future_copy)
        self.future_table = QTableWidget(0, len(self.FUTURE_HEADERS))
        self.future_table.setObjectName("DashboardTable")
        self.future_table.setProperty("managerTable", True)
        self.future_table.setHorizontalHeaderLabels(list(self.FUTURE_HEADERS))
        self.future_table.setAlternatingRowColors(True)
        self.future_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.future_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.future_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.future_table.setShowGrid(False)
        self.future_table.verticalHeader().setVisible(False)
        self.future_table.verticalHeader().setDefaultSectionSize(34)
        self.future_table.horizontalHeader().setStretchLastSection(True)
        for column_index in range(len(self.FUTURE_HEADERS)):
            self.future_table.horizontalHeader().setSectionResizeMode(
                column_index,
                QHeaderView.ResizeMode.Stretch,
            )
        future_table_row = QHBoxLayout()
        future_table_row.setContentsMargins(0, 0, 0, 0)
        future_table_row.setSpacing(0)
        future_table_row.addWidget(self.future_table, stretch=9)
        future_table_row.addStretch(1)
        future_layout.addLayout(future_table_row)
        future_layout.addStretch(1)

        customer_card = QFrame()
        customer_card.setObjectName("InnerCard")
        customer_card.setProperty("managerPanel", True)
        customer_layout = QVBoxLayout(customer_card)
        customer_layout.setContentsMargins(28, 28, 28, 28)
        customer_layout.setSpacing(16)
        customer_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        search_title = QLabel("Customer Search")
        search_title.setObjectName("SectionTitle")
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, phone number or email")
        self.search_input.setMinimumWidth(180)
        self.search_input.setMinimumHeight(52)
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("ActionButton")
        self.search_button.setMinimumHeight(48)
        self.search_button.setMinimumWidth(160)
        self.add_customer_button = QPushButton("Add New")
        self.add_customer_button.setObjectName("SecondaryButton")
        self.add_customer_button.setMinimumHeight(48)
        self.add_customer_button.setMinimumWidth(160)
        search_row.addWidget(self.search_input, stretch=1)
        search_row.addWidget(self.search_button, stretch=1)
        search_row.addWidget(self.add_customer_button, stretch=1)
        search_copy = QLabel(
            "Only customers created inside the active store are shown here. Use Add New to create a customer."
        )
        search_copy.setObjectName("SectionCopy")
        search_copy.setWordWrap(True)
        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("StatusMessage")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.hide()
        self.customer_table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.customer_table.setObjectName("DashboardTable")
        self.customer_table.setProperty("managerTable", True)
        self.customer_table.setHorizontalHeaderLabels(list(self.TABLE_HEADERS))
        self.customer_table.setAlternatingRowColors(True)
        self.customer_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.customer_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.customer_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.customer_table.setShowGrid(False)
        self.customer_table.verticalHeader().setVisible(False)
        self.customer_table.verticalHeader().setDefaultSectionSize(36)
        self.customer_table.horizontalHeader().setStretchLastSection(True)
        for column_index in range(len(self.TABLE_HEADERS)):
            self.customer_table.horizontalHeader().setSectionResizeMode(
                column_index,
                QHeaderView.ResizeMode.Stretch,
            )
        pagination_row = QHBoxLayout()
        pagination_row.setContentsMargins(0, 0, 0, 0)
        pagination_row.setSpacing(10)
        self.pagination_label = QLabel("")
        self.pagination_label.setObjectName("SectionCopy")
        self.previous_page_button = QPushButton("Previous")
        self.previous_page_button.setObjectName("SecondaryButton")
        self.previous_page_button.setMinimumHeight(34)
        self.previous_page_button.setMinimumWidth(96)
        self.page_buttons_container = QWidget()
        page_buttons_layout = QHBoxLayout(self.page_buttons_container)
        page_buttons_layout.setContentsMargins(0, 0, 0, 0)
        page_buttons_layout.setSpacing(8)
        self._page_buttons_layout = page_buttons_layout
        self._page_buttons: list[QPushButton] = []
        self.next_page_button = QPushButton("Next")
        self.next_page_button.setObjectName("SecondaryButton")
        self.next_page_button.setMinimumHeight(34)
        self.next_page_button.setMinimumWidth(96)
        pagination_row.addWidget(self.pagination_label, stretch=1)
        pagination_row.addWidget(self.previous_page_button)
        pagination_row.addWidget(self.page_buttons_container)
        pagination_row.addWidget(self.next_page_button)
        customer_layout.addWidget(search_title)
        customer_layout.addLayout(search_row)
        customer_layout.addWidget(search_copy)
        customer_layout.addWidget(self.feedback_label)
        customer_layout.addWidget(self.customer_table)
        customer_layout.addLayout(pagination_row)
        customer_layout.addStretch(1)

        layout.addWidget(customer_card, 0, 0)
        layout.addWidget(future_card, 0, 1)
        root.addLayout(layout, stretch=1)

        self.search_input.returnPressed.connect(self._apply_search)
        self.search_input.textChanged.connect(self._handle_search_text_changed)
        self.search_button.clicked.connect(self._apply_search)
        self.add_customer_button.clicked.connect(self._open_add_customer_dialog)
        self.previous_page_button.clicked.connect(self._show_previous_page)
        self.next_page_button.clicked.connect(self._show_next_page)
        _apply_compact_table_style(self.future_table, row_height=28, embedded=True)
        _apply_compact_table_style(self.customer_table, row_height=28, embedded=True)
        self.clear_context()

    def set_context(
        self,
        *,
        current_user_id: str | None,
        store_context: StoreDashboardContext,
    ) -> None:
        self._current_user_id = current_user_id
        self._store_context = store_context
        self._set_feedback("", tone="success")
        self.refresh_data()

    def clear_context(self) -> None:
        self._current_user_id = None
        self._store_context = None
        self._all_rows = ()
        self._cached_rows_by_id = {}
        self._visible_customer_rows = ()
        self._current_page = 0
        self._total_customer_rows = 0
        self._active_query = ""
        self._database_search_active = False
        self._order_queue_rows = ()
        self.search_input.clear()
        self.search_input.setEnabled(False)
        self.search_button.setEnabled(False)
        self.add_customer_button.setEnabled(False)
        self.previous_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)
        self.pagination_label.setText("")
        self._set_feedback("", tone="success")
        self._set_table_rows(())
        self._set_future_table_rows(())

    def refresh_data(self) -> None:
        if self._store_context is None:
            self.clear_context()
            return
        self.search_input.setEnabled(True)
        self.search_button.setEnabled(True)
        self.add_customer_button.setEnabled(True)
        self._cached_rows_by_id = {}
        self._active_query = ""
        self._database_search_active = False
        self._load_customer_page(page=0)
        self._refresh_order_queue()

    def _apply_search(self) -> None:
        if self._store_context is None:
            self._set_table_rows(())
            return
        query = self.search_input.text().strip().lower()
        if not query:
            self._load_customer_page(page=0)
            return

        cached_matches = self._filter_cached_rows(query)
        self._active_query = query
        self._current_page = 0
        if cached_matches:
            self._database_search_active = False
            self._all_rows = cached_matches
            self._total_customer_rows = len(cached_matches)
            self._show_cached_page(page=0)
            return

        self._database_search_active = True
        self._total_customer_rows = self._operations_service.count_search_customer_summaries_for_store(
            store_id=self._store_context.store_id,
            query=query,
        )
        self._load_database_search_page(page=0)

    def _handle_search_text_changed(self, text: str) -> None:
        if text.strip():
            return
        if self._store_context is not None:
            self._load_customer_page(page=0)

    def _show_previous_page(self) -> None:
        if self._current_page <= 0:
            return
        self._load_active_page(self._current_page - 1)

    def _show_next_page(self) -> None:
        if (self._current_page + 1) * self.CUSTOMER_PAGE_SIZE >= self._total_customer_rows:
            return
        self._load_active_page(self._current_page + 1)

    def _load_active_page(self, page: int) -> None:
        if self._active_query and self._database_search_active:
            self._load_database_search_page(page=page)
            return
        if self._active_query:
            self._show_cached_page(page=page)
            return
        self._load_customer_page(page=page)

    def _load_customer_page(self, *, page: int) -> None:
        if self._store_context is None:
            self._set_table_rows(())
            return
        self._active_query = ""
        self._database_search_active = False
        self._current_page = max(0, page)
        self._total_customer_rows = self._operations_service.count_customer_summaries_for_store(
            store_id=self._store_context.store_id
        )
        rows = tuple(
            self._to_manager_customer_summary(row)
            for row in self._operations_service.list_customer_summaries_for_store(
                store_id=self._store_context.store_id,
                limit=self.CUSTOMER_PAGE_SIZE,
                offset=self._current_page * self.CUSTOMER_PAGE_SIZE,
            )
        )
        self._cache_rows(rows)
        self._all_rows = rows
        self._visible_customer_rows = rows
        self._set_table_rows(rows)

    def _load_database_search_page(self, *, page: int) -> None:
        if self._store_context is None:
            self._set_table_rows(())
            return
        self._current_page = max(0, page)
        rows = tuple(
            self._to_manager_customer_summary(row)
            for row in self._operations_service.search_customer_summaries_for_store(
                store_id=self._store_context.store_id,
                query=self._active_query,
                limit=self.CUSTOMER_PAGE_SIZE,
                offset=self._current_page * self.CUSTOMER_PAGE_SIZE,
            )
        )
        self._cache_rows(rows)
        self._all_rows = rows
        self._visible_customer_rows = rows
        self._set_table_rows(rows)

    def _show_cached_page(self, *, page: int) -> None:
        self._current_page = max(0, page)
        start = self._current_page * self.CUSTOMER_PAGE_SIZE
        end = start + self.CUSTOMER_PAGE_SIZE
        rows = self._all_rows[start:end]
        self._visible_customer_rows = rows
        self._set_table_rows(rows)

    def _filter_cached_rows(self, query: str) -> tuple[ManagerCustomerSummary, ...]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return ()
        return tuple(
            row
            for row in self._cached_rows_by_id.values()
            if normalized_query in row.full_name.lower()
            or normalized_query in row.mobile.lower()
            or normalized_query in row.email.lower()
        )

    def _cache_rows(self, rows: tuple[ManagerCustomerSummary, ...]) -> None:
        for row in rows:
            self._cached_rows_by_id[row.customer_id] = row

    def _set_table_rows(self, rows: tuple[ManagerCustomerSummary, ...]) -> None:
        self.customer_table.setUpdatesEnabled(False)
        self.customer_table.clearSpans()
        self.customer_table.clearContents()
        try:
            if not rows:
                self.customer_table.setRowCount(1)
                self.customer_table.setSpan(0, 0, 1, self.customer_table.columnCount())
                empty_item = QTableWidgetItem(
                    "No customers found for this store. Use Add New to create the first customer."
                )
                empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.customer_table.setItem(0, 0, empty_item)
                for column_index in range(1, self.customer_table.columnCount()):
                    self.customer_table.setItem(0, column_index, QTableWidgetItem(""))
                self._set_table_visible_height(
                    self.customer_table,
                    visible_rows=self.CUSTOMER_VISIBLE_ROWS,
                )
                return

            self.customer_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                row_values = (
                    row.full_name,
                    row.mobile,
                    row.last_order_on.astimezone(timezone.utc).strftime("%Y-%m-%d")
                    if row.last_order_on is not None
                    else "--",
                    f"INR {row.balance_amount:,.2f}",
                )
                for column_index, value in enumerate(row_values):
                    item = QTableWidgetItem(value)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        if column_index == 3
                        else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.customer_table.setItem(row_index, column_index, item)
            self._set_table_visible_height(
                self.customer_table,
                visible_rows=self.CUSTOMER_VISIBLE_ROWS,
            )
            self._refresh_pagination_controls()
        finally:
            self.customer_table.setUpdatesEnabled(True)
            self._refresh_pagination_controls()

    def _set_future_table_rows(self, rows: tuple[ManagerOrderQueueRow, ...]) -> None:
        self.future_table.setUpdatesEnabled(False)
        self.future_table.clearSpans()
        self.future_table.clearContents()
        try:
            if not rows:
                self.future_table.setRowCount(1)
                self.future_table.setSpan(0, 0, 1, self.future_table.columnCount())
                empty_item = QTableWidgetItem("No store orders available yet.")
                empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.future_table.setItem(0, 0, empty_item)
                for column_index in range(1, self.future_table.columnCount()):
                    self.future_table.setItem(0, column_index, QTableWidgetItem(""))
                self._set_table_visible_height(
                    self.future_table,
                    visible_rows=self.FUTURE_VISIBLE_ROWS,
                )
                return

            self.future_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                row_values = (
                    row.customer_name,
                    row.order_date.astimezone(timezone.utc).strftime("%Y-%m-%d"),
                    row.due_date.astimezone(timezone.utc).strftime("%Y-%m-%d")
                    if row.due_date is not None
                    else "--",
                    row.priority,
                    row.item_name,
                )
                for column_index, value in enumerate(row_values):
                    item = QTableWidgetItem(value)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self.future_table.setItem(row_index, column_index, item)
            self._set_table_visible_height(
                self.future_table,
                visible_rows=self.FUTURE_VISIBLE_ROWS,
            )
        finally:
            self.future_table.setUpdatesEnabled(True)

    def _open_add_customer_dialog(self) -> None:
        if self._current_user_id is None or self._store_context is None:
            return
        item_rows = self._operations_service.list_items(store_id=self._store_context.store_id)
        if not item_rows:
            self._set_feedback("Create store items before creating a customer order.", tone="error")
            return

        creator_name = self._user_management_service.display_name_for_user(self._current_user_id)
        dialog = CustomerOrderEntryDialog(
            item_rows=item_rows,
            created_by_name=creator_name or "Current manager",
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.payload()
            order_items = payload["items"]
            if not isinstance(order_items, tuple) or not order_items:
                dialog.set_feedback("Add at least one order item before saving.", tone="error")
                continue
            order_input = CustomerOrderCreateInput(
                title=self._default_order_title(order_items),
                created_by=str(payload["created_by"]),
                due_on=payload["due_on"],  # type: ignore[arg-type]
                priority=str(payload["priority"]),
                status=str(payload["order_status"]),
                paid_amount=payload["paid_amount"],  # type: ignore[arg-type]
                items=order_items,
            )
            try:
                self._operations_service.create_customer_with_orders(
                    store_id=self._store_context.store_id,
                    full_name=str(payload["full_name"]),
                    mobile=str(payload["mobile"]),
                    email="",
                    address=str(payload["address"]),
                    is_whatsapp=bool(payload["whatsapp_enabled"]),
                    orders=[order_input],
                )
            except ValueError as exc:
                dialog.set_feedback(str(exc), tone="error")
                continue

            self._set_feedback("Customer and order created successfully.", tone="success")
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
            self._active_query = ""
            self._database_search_active = False
            self._cached_rows_by_id = {}
            self._load_customer_page(page=0)
            self._refresh_order_queue()
            break

    def _default_order_title(self, items: tuple[OrderItemCreateInput, ...]) -> str:
        if len(items) == 1:
            return items[0].item_name
        return f"{items[0].item_name} + {len(items) - 1} more item(s)"

    def _to_manager_customer_summary(self, row: CustomerSummaryRow) -> ManagerCustomerSummary:
        return ManagerCustomerSummary(
            customer_id=row.customer_id,
            full_name=row.full_name,
            mobile=row.mobile,
            email=row.email,
            last_order_on=row.last_order_on,
            balance_amount=row.balance_amount,
        )

    def _to_manager_order_queue_row(self, row: OrderQueueRow) -> ManagerOrderQueueRow:
        return ManagerOrderQueueRow(
            customer_name=row.customer_name,
            order_date=row.order_date,
            due_date=row.due_date,
            priority=row.priority,
            item_name=row.item_name,
            status=row.status,
        )

    def _refresh_order_queue(self) -> None:
        if self._store_context is None:
            self._set_future_table_rows(())
            return
        self._order_queue_rows = tuple(
            self._to_manager_order_queue_row(row)
            for row in self._operations_service.list_order_queue_for_store(
                store_id=self._store_context.store_id
            )
        )
        self._set_future_table_rows(self._order_queue_rows)

    def _set_feedback(self, message: str, *, tone: str) -> None:
        self._feedback_clear_timer.stop()
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(bool(message))
        self.feedback_label.setProperty("tone", tone)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.update()
        if message:
            self._feedback_clear_timer.start(30_000)

    def _set_table_visible_height(self, table: QTableWidget, *, visible_rows: int) -> None:
        row_count = max(1, table.rowCount())
        shown_rows = min(row_count, visible_rows)
        header_height = table.horizontalHeader().sizeHint().height()
        frame_height = table.frameWidth() * 2
        height = header_height + (table.verticalHeader().defaultSectionSize() * shown_rows) + frame_height
        table.setMinimumHeight(0)
        table.setMaximumHeight(height)

    def _refresh_pagination_controls(self) -> None:
        total_pages = max(
            1,
            (self._total_customer_rows + self.CUSTOMER_PAGE_SIZE - 1) // self.CUSTOMER_PAGE_SIZE,
        )
        current_page = min(self._current_page + 1, total_pages)
        if self._total_customer_rows == 0:
            self.pagination_label.setText("Showing 0 to 0 of 0 entries")
        else:
            start = (self._current_page * self.CUSTOMER_PAGE_SIZE) + 1
            end = min(
                start + len(self._visible_customer_rows) - 1,
                self._total_customer_rows,
            )
            self.pagination_label.setText(
                f"Showing {start} to {end} of {self._total_customer_rows} entries"
            )
        self.previous_page_button.setEnabled(self._current_page > 0)
        self.next_page_button.setEnabled(
            (self._current_page + 1) * self.CUSTOMER_PAGE_SIZE < self._total_customer_rows
        )
        self._render_page_buttons(total_pages=total_pages, current_page=current_page)

    def _render_page_buttons(self, *, total_pages: int, current_page: int) -> None:
        while self._page_buttons_layout.count():
            item = self._page_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._page_buttons = []
        if self._total_customer_rows == 0:
            self.page_buttons_container.hide()
            return

        self.page_buttons_container.show()
        for page_number in self._visible_page_numbers(total_pages=total_pages, current_page=current_page):
            button = QPushButton(str(page_number))
            button.setObjectName("PageButton")
            button.setCheckable(True)
            button.setChecked(page_number == current_page)
            button.setMinimumSize(38, 34)
            button.setMaximumWidth(44)
            button.clicked.connect(
                lambda _checked=False, number=page_number: self._load_active_page(number - 1)
            )
            self._page_buttons_layout.addWidget(button)
            self._page_buttons.append(button)

    def _visible_page_numbers(self, *, total_pages: int, current_page: int) -> tuple[int, ...]:
        if total_pages <= 5:
            return tuple(range(1, total_pages + 1))
        start = max(1, min(current_page - 2, total_pages - 4))
        return tuple(range(start, start + 5))

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QFrame#InnerCard[managerPanel="true"] {
                background-color: #f3ece4;
                border: 1px solid #dccdbd;
                border-radius: 18px;
            }
            QLabel#SectionTitle {
                font-size: 20px;
                font-weight: 700;
                color: #071b2c;
            }
            QLabel#SectionCopy {
                font-size: 16px;
                color: #334155;
            }
            QLineEdit {
                min-height: 48px;
                padding: 0 16px;
                border: 1px solid #9a632b;
                border-radius: 14px;
                background-color: #fffdfa;
                color: #071b2c;
            }
            QPushButton#ActionButton {
                min-height: 48px;
                border-radius: 16px;
                background-color: #9a632b;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton#ActionButton:hover {
                background-color: #865321;
            }
            QPushButton#SecondaryButton {
                min-height: 34px;
                border: 1px solid #dfe3ea;
                border-radius: 4px;
                background-color: #eee5da;
                color: #5c67f2;
                font-weight: 600;
                padding: 0 14px;
            }
            QPushButton#SecondaryButton:hover {
                background-color: #f4f1ec;
            }
            QPushButton#SecondaryButton:disabled {
                background-color: #e5e7eb;
                color: #6b7280;
            }
            QPushButton#PageButton {
                min-width: 38px;
                min-height: 34px;
                border: 1px solid #dfe3ea;
                border-radius: 0;
                background-color: #ffffff;
                color: #5c67f2;
                font-weight: 600;
                padding: 0;
            }
            QPushButton#PageButton:hover {
                background-color: #f7f8ff;
            }
            QPushButton#PageButton:checked {
                background-color: #5c67f2;
                border-color: #5c67f2;
                color: #ffffff;
            }
            QTableWidget#DashboardTable[managerTable="true"] {
                background-color: #fffdfa;
                alternate-background-color: #fbf6ef;
                border: none;
                color: #071b2c;
                gridline-color: #eadfce;
                outline: none;
            }
            QTableWidget#DashboardTable[managerTable="true"]::item {
                padding: 8px 10px;
                border-bottom: 1px solid #eadfce;
            }
            QTableWidget#DashboardTable[managerTable="true"] QHeaderView::section {
                background-color: #e8ddd0;
                color: #1f130a;
                border: none;
                border-bottom: 1px solid #d6c6b5;
                padding: 10px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            """
        )
