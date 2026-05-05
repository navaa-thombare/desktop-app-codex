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
    QButtonGroup,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.admin.services import AdminUserManagementService, StoreDashboardContext
from app.desktop_shell.ui.action_logging import (
    attach_action_logging,
    install_action_logging,
    log_ui_action,
)
from app.desktop_shell.i18n import apply_widget_translations, tr, translate_table_headers
from app.operations.services import (
    CustomerOrderHistoryRow,
    CustomerOrderCreateInput,
    CustomerRow,
    CustomerSummaryRow,
    ItemRow,
    MeasurementRow,
    OrderQueueRow,
    PaymentHistoryRow,
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
    measurement_id: int | None = None

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
        table.setLineWidth(0)
        table.setMidLineWidth(0)
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
        customer: CustomerRow | None = None,
        measurement_rows: tuple[MeasurementRow, ...] = (),
        language_code: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._language_code = language_code
        self._item_lookup = {row.item_id: row for row in item_rows}
        self._existing_customer = customer
        self._measurement_rows = measurement_rows
        self._measurement_lookup = {row.measurement_id: row for row in measurement_rows}
        self._created_by_name = created_by_name.strip() or "Current manager"
        self._draft_items: list[ManagerOrderItemDraft] = []
        self._order_created_on = datetime.now(tz=timezone.utc)
        self._feedback_clear_timer = QTimer(self)
        self._feedback_clear_timer.setSingleShot(True)
        self._feedback_clear_timer.timeout.connect(
            lambda: self.set_feedback("", tone="success")
        )
        self.setModal(True)
        self.setWindowTitle(tr("Add New Order" if customer is not None else "Add New Customer", language_code))
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
        title = QLabel("Add New Order" if customer is not None else "Add New Customer")
        title.setObjectName("DialogTitle")
        copy = QLabel(
            f"Create a new order for {customer.full_name}"
            if customer is not None
            else "Enter customer details, order metadata and items"
        )
        copy.setObjectName("DialogSubtitle")
        copy.setWordWrap(True)
        header_copy.addWidget(title)
        header_copy.addWidget(copy)
        header.addWidget(icon)
        header.addLayout(header_copy, stretch=1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("DialogSecondaryButton")
        self.save_button = QPushButton("Save Order" if customer is not None else "Save Customer")
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
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("Customer weight")
        initial_weight = self._measurement_weight()
        if initial_weight is not None:
            self.weight_input.setText(f"{initial_weight:,.2f}")
        self._dialog_control(
            self.due_date_input,
            self.priority_combo,
            self.weight_input,
        )

        metadata_form.addWidget(self._field_block("Due Date *", self.due_date_input), 0, 0)
        metadata_form.addWidget(self._field_block("Priority *", self.priority_combo), 0, 1)
        metadata_form.addWidget(self._field_block("Weight", self.weight_input), 1, 0, 1, 2)
        metadata_layout.addWidget(metadata_title)
        metadata_layout.addLayout(metadata_form)

        if customer is None:
            top_sections.addWidget(customer_card, 0, 0)
            top_sections.addWidget(metadata_card, 0, 1)
        else:
            top_sections.addWidget(metadata_card, 0, 0, 1, 2)

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
        if customer is None:
            self.measurements_input = QLineEdit()
            self.measurements_input.setPlaceholderText("Enter measurements")
        else:
            self.measurements_input = QComboBox()
            self.measurements_input.setObjectName("MeasurementSelect")
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
        self.paid_amount_input.setObjectName("AmountPaidInput")
        self.paid_amount_input.setPlaceholderText("Enter amount")
        self.balance_amount_input = self._summary_value("0.00")
        self._dialog_control(self.paid_amount_input)
        summary_row.addWidget(self._summary_block("Bill Amount (INR)", self.bill_amount_input))
        summary_row.addWidget(self._summary_block("Amount Paid (INR)", self.paid_amount_input))
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
        self.item_combo.currentIndexChanged.connect(self._refresh_measurement_options)
        self.quantity_input.valueChanged.connect(self._refresh_item_defaults)
        self.paid_amount_input.textChanged.connect(self._update_bill_amount)
        self._refresh_item_defaults()
        self._refresh_measurement_options()
        self._refresh_items_table()
        self._update_bill_amount()
        apply_widget_translations(self, language_code)
        translate_table_headers(self.items_table, self.ITEM_HEADERS, language_code)
        install_action_logging(self, screen=self.__class__.__name__)

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
                measurement_id=draft.measurement_id,
            )
            for draft in self._draft_items
        )
        return {
            "full_name": "" if self._existing_customer is not None else self.full_name_input.text().strip(),
            "mobile": "" if self._existing_customer is not None else self.mobile_input.text().strip(),
            "address": "" if self._existing_customer is not None else self.address_input.toPlainText().strip(),
            "whatsapp_enabled": False if self._existing_customer is not None else self.whatsapp_checkbox.isChecked(),
            "created_on": self._order_created_on,
            "created_by": self._created_by_name,
            "due_on": due_on,
            "priority": self.priority_combo.currentText().strip(),
            "order_status": "NEW",
            "weight": self._parse_weight(self.weight_input.text()),
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
        log_ui_action(
            self.__class__.__name__,
            "save_order_dialog",
            item_count=len(self._draft_items),
            existing_customer=bool(self._existing_customer),
        )
        if self._existing_customer is None and not self.full_name_input.text().strip():
            self.set_feedback("Full name is required.", tone="error")
            return
        if self._existing_customer is None and not self.mobile_input.text().strip():
            self.set_feedback("Contact number is required.", tone="error")
            return
        if self._existing_customer is None and not self.address_input.toPlainText().strip():
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
        try:
            self._parse_weight(self.weight_input.text())
        except ValueError as exc:
            self.set_feedback(str(exc), tone="error")
            return
        if paid_amount > self._bill_amount():
            self.set_feedback("Paid amount cannot be greater than bill amount.", tone="error")
            return
        self.accept()

    def _add_item(self) -> None:
        log_ui_action(self.__class__.__name__, "add_order_item")
        item_row = self._selected_item_row()
        if item_row is None:
            self.set_feedback("Select an item before adding it.", tone="error")
            return
        if self._existing_customer is not None and self._current_measurement_id() is None:
            self.set_feedback("Select a saved measurement before adding this item.", tone="error")
            return
        updated_on = datetime.now(tz=timezone.utc)
        self._draft_items.append(
            ManagerOrderItemDraft(
                item_id=item_row.item_id,
                item_name=item_row.item_name,
                quantity=self.quantity_input.value(),
                measurements=self._current_measurement_text(),
                rate=item_row.cost,
                status="NEW",
                updated_on=updated_on,
                updated_by=self._created_by_name,
                measurement_id=self._current_measurement_id(),
            )
        )
        self._reset_item_entry()
        self._update_bill_amount()
        self._refresh_items_table()
        self.set_feedback("Item added to the order.", tone="success")

    def _reset_item_entry(self) -> None:
        log_ui_action(self.__class__.__name__, "reset_order_item_entry")
        self.quantity_input.setValue(1)
        self.item_combo.setCurrentIndex(0)
        if isinstance(self.measurements_input, QLineEdit):
            self.measurements_input.clear()
        self._refresh_item_defaults()
        self._refresh_measurement_options()

    def _remove_selected_item(self) -> None:
        log_ui_action(self.__class__.__name__, "remove_selected_order_item")
        current_row = self.items_table.currentRow()
        if current_row < 0 or current_row >= len(self._draft_items):
            self.set_feedback("Select an item row before removing it.", tone="error")
            return
        del self._draft_items[current_row]
        self._update_bill_amount()
        self._refresh_items_table()
        self.set_feedback("Removed the selected order item.", tone="success")

    def _selected_item_row(self) -> ItemRow | None:
        item_id = self.item_combo.currentData()
        if not isinstance(item_id, str) or not item_id:
            return None
        return self._item_lookup.get(item_id)

    def _refresh_item_defaults(self) -> None:
        selected_item = self._selected_item_row()
        self.add_item_button.setEnabled(selected_item is not None)

    def _refresh_measurement_options(self) -> None:
        if not isinstance(self.measurements_input, QComboBox):
            return
        selected_item = self._selected_item_row()
        selected_item_id = selected_item.item_id if selected_item is not None else ""
        self.measurements_input.blockSignals(True)
        self.measurements_input.clear()
        self.measurements_input.addItem("Select measurement", None)
        for row in self._measurement_rows:
            if (
                row.item_id == selected_item_id
                and row.measurement_id is not None
                and row.measurements.strip()
            ):
                self.measurements_input.addItem(row.measurements, row.measurement_id)
        self.measurements_input.blockSignals(False)

    def _current_measurement_id(self) -> int | None:
        if not isinstance(self.measurements_input, QComboBox):
            return None
        value = self.measurements_input.currentData()
        return value if isinstance(value, int) else None

    def _current_measurement_text(self) -> str:
        if isinstance(self.measurements_input, QComboBox):
            measurement_id = self._current_measurement_id()
            if measurement_id is None:
                return ""
            measurement = self._measurement_lookup.get(measurement_id)
            return measurement.measurements if measurement is not None else ""
        return self.measurements_input.text().strip()

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
        if bill_amount <= Decimal("0.00"):
            if self.paid_amount_input.isEnabled():
                self.paid_amount_input.setEnabled(False)
            if self.paid_amount_input.text() != "0.00":
                self.paid_amount_input.blockSignals(True)
                self.paid_amount_input.setText("0.00")
                self.paid_amount_input.blockSignals(False)
            self.balance_amount_input.setText("0.00")
            return
        if not self.paid_amount_input.isEnabled():
            self.paid_amount_input.setEnabled(True)
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

    def _parse_weight(self, value: str) -> Decimal | None:
        normalized_value = value.strip().replace(",", "")
        if not normalized_value:
            return None
        try:
            parsed = Decimal(normalized_value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Enter a valid customer weight.") from exc
        if parsed < Decimal("0.00"):
            raise ValueError("Customer weight cannot be negative.")
        return parsed.quantize(Decimal("0.01"))

    def _measurement_weight(self) -> Decimal | None:
        for row in self._measurement_rows:
            if row.weight is not None:
                return row.weight
        return None

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
        widget.setObjectName("SummaryReadonlyAmount")
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
            QTableWidget#DialogItemsTable::item:selected {
                background-color: #eef2ff;
                color: #111827;
            }
            QTableWidget#DialogItemsTable QRadioButton {
                background-color: transparent;
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
            QLineEdit#SummaryReadonlyAmount {
                min-width: 92px;
                min-height: 20px;
                border: none;
                background-color: transparent;
                color: #111827;
                font-size: 8pt;
                font-weight: 300;
                padding: 0;
            }
            QLineEdit#SummaryReadonlyAmount:focus {
                border: none;
            }
            QLineEdit#AmountPaidInput {
                min-width: 118px;
                min-height: 34px;
                border: 1px solid #dfe3ec;
                border-radius: 7px;
                background-color: #ffffff;
                color: #111827;
                font-size: 9pt;
                font-weight: 500;
                padding: 0 10px;
            }
            QLineEdit#AmountPaidInput:focus {
                border: 1px solid #4f46e5;
            }
            QLineEdit#AmountPaidInput:disabled {
                background-color: #f8fafc;
                color: #98a2b3;
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


class CustomerDetailsDialog(QDialog):
    ORDER_HEADERS = (
        "",
        "Order ID",
        "Order Date",
        "Total Items",
        "Paid Amount",
        "Amount",
        "Balance Amount",
        "Bill Status",
        "Status",
    )
    PAYMENT_HEADERS = (
        "Order ID",
        "Payment Date",
        "Paid Amount",
        "Notes",
    )
    MEASUREMENT_HEADERS = (
        "Item",
        "Measurements",
        "Weight",
        "Measurement Date",
    )

    def __init__(
        self,
        *,
        customer: CustomerRow,
        order_history: tuple[CustomerOrderHistoryRow, ...],
        payment_history: tuple[PaymentHistoryRow, ...],
        measurement_rows: tuple[MeasurementRow, ...],
        operations_service: OperationsService,
        store_id: str,
        created_by_name: str,
        language_code: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._language_code = language_code
        self._customer = customer
        self._order_history = order_history
        self._payment_history = payment_history
        self._measurement_rows = measurement_rows
        self._operations_service = operations_service
        self._store_id = store_id
        self._created_by_name = created_by_name.strip() or "Current manager"
        self._order_summaries = self._build_order_summaries()
        self._selected_order_id = str(self._order_summaries[0]["order_id"]) if self._order_summaries else ""
        self._order_radio_buttons: list[QRadioButton] = []
        self.setModal(True)
        self.setWindowTitle("Customer Details")
        self.setMinimumSize(1040, 500)
        self.resize(1180, 560)
        self._apply_dialog_styles()

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(8)

        total_bill = customer.total_billing
        paid_amount = customer.received_amount
        balance_amount = (total_bill - paid_amount).quantize(Decimal("0.01"))
        total_orders = len({row.order_id for row in order_history})

        header_card = QFrame()
        header_card.setObjectName("DetailSummaryBar")
        header_card.setFixedHeight(66)
        header_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header = QHBoxLayout(header_card)
        header.setContentsMargins(4, 4, 4, 4)
        header.setSpacing(10)
        avatar = QLabel(self._initials(customer.full_name))
        avatar.setObjectName("DetailAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(42, 42)
        title_block = QVBoxLayout()
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(4)
        title = QLabel(customer.full_name)
        title.setObjectName("DetailTitle")
        customer_id = QLabel(customer.customer_id)
        customer_id.setObjectName("DetailMeta")
        title_block.addWidget(title)
        title_block.addWidget(customer_id)

        contact_block = QVBoxLayout()
        contact_block.setContentsMargins(0, 0, 0, 0)
        contact_block.setSpacing(3)
        phone = QLabel(f"Phone: {customer.mobile or '--'}")
        phone.setObjectName("DetailMeta")
        address = QLabel(f"Address: {customer.address or '--'}")
        address.setObjectName("DetailMeta")
        address.setWordWrap(True)
        contact_block.addWidget(phone)
        contact_block.addWidget(address)

        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("DialogSecondaryButton")
        self.close_button.setFixedSize(104, 32)

        header.addWidget(avatar)
        header.addLayout(title_block, stretch=2)
        header.addWidget(self._summary_separator())
        header.addLayout(contact_block, stretch=3)
        header.addWidget(self._summary_separator())
        header.addWidget(self._summary_metric(str(total_orders), "TOTAL ORDERS"))
        header.addWidget(self._summary_separator())
        header.addWidget(self._summary_metric(self._format_currency(total_bill), "TOTAL BILL"))
        header.addWidget(self._summary_separator())
        header.addWidget(self._summary_metric(self._format_currency(paid_amount), "PAID AMOUNT"))
        header.addWidget(self._summary_separator())
        header.addWidget(self._summary_metric(self._format_currency(balance_amount), "BALANCE AMOUNT"))
        header.addWidget(self.close_button)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(10)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(7)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 2, 0, 0)
        tab_row.setSpacing(6)
        self.orders_tab_button = QPushButton("Orders")
        self.orders_tab_button.setObjectName("DetailTabButton")
        self.orders_tab_button.setCheckable(True)
        self.orders_tab_button.setChecked(True)
        self.payments_tab_button = QPushButton("Payments")
        self.payments_tab_button.setObjectName("DetailTabButton")
        self.payments_tab_button.setCheckable(True)
        self.new_order_button = QPushButton("New Order")
        self.new_order_button.setObjectName("DetailOutlineButton")
        self.measurements_tab_button = QPushButton("Measurements")
        self.measurements_tab_button.setObjectName("DetailTabButton")
        self.measurements_tab_button.setCheckable(True)
        self.save_measurements_button = QPushButton("Save Measurements")
        self.save_measurements_button.setObjectName("DetailOutlineButton")
        self.save_measurements_button.hide()
        tab_row.addWidget(self.orders_tab_button)
        tab_row.addWidget(self.measurements_tab_button)
        tab_row.addWidget(self.payments_tab_button)
        tab_row.addWidget(self.new_order_button)
        tab_row.addStretch(1)
        tab_row.addWidget(self.save_measurements_button)

        self.content_stack = QStackedWidget()

        self.orders_table = QTableWidget(0, len(self.ORDER_HEADERS))
        self.orders_table.setObjectName("DialogItemsTable")
        self.orders_table.setHorizontalHeaderLabels(list(self.ORDER_HEADERS))
        self.orders_table.setAlternatingRowColors(True)
        self.orders_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.orders_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.orders_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.orders_table.setShowGrid(False)
        self.orders_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.orders_table.verticalHeader().setVisible(False)
        self.orders_table.verticalHeader().setDefaultSectionSize(24)
        self.orders_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.orders_table.horizontalHeader().setMinimumSectionSize(28)
        self.orders_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.orders_table.setColumnWidth(0, 34)
        self.orders_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.orders_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.orders_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        _apply_compact_table_style(self.orders_table, row_height=24)
        self.orders_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._set_order_summary_rows()

        self.payments_table = QTableWidget(0, len(self.PAYMENT_HEADERS))
        self.payments_table.setObjectName("DialogItemsTable")
        self.payments_table.setHorizontalHeaderLabels(list(self.PAYMENT_HEADERS))
        self.payments_table.setAlternatingRowColors(True)
        self.payments_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.payments_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.payments_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.payments_table.setShowGrid(False)
        self.payments_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.verticalHeader().setDefaultSectionSize(24)
        self.payments_table.horizontalHeader().setStretchLastSection(True)
        for column_index in range(len(self.PAYMENT_HEADERS)):
            self.payments_table.horizontalHeader().setSectionResizeMode(
                column_index,
                QHeaderView.ResizeMode.Stretch,
            )
        _apply_compact_table_style(self.payments_table, row_height=24)
        self.payments_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._set_payment_rows()

        self.measurements_table = QTableWidget(0, len(self.MEASUREMENT_HEADERS))
        self.measurements_table.setObjectName("DialogItemsTable")
        self.measurements_table.setHorizontalHeaderLabels(list(self.MEASUREMENT_HEADERS))
        self.measurements_table.setAlternatingRowColors(True)
        self.measurements_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.measurements_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.measurements_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.measurements_table.setShowGrid(False)
        self.measurements_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.measurements_table.verticalHeader().setVisible(False)
        self.measurements_table.verticalHeader().setDefaultSectionSize(24)
        self.measurements_table.horizontalHeader().setStretchLastSection(True)
        self.measurements_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.measurements_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.measurements_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.measurements_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        _apply_compact_table_style(self.measurements_table, row_height=24)
        self.measurements_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._set_measurement_rows()

        self.content_stack.addWidget(self.orders_table)
        self.content_stack.addWidget(self.measurements_table)
        self.content_stack.addWidget(self.payments_table)
        left_layout.addLayout(tab_row)
        left_layout.addWidget(self.content_stack, stretch=1)

        right_panel = QWidget()
        right_panel.setObjectName("DetailSummaryPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 35, 0, 0)
        right_layout.setSpacing(7)
        self.current_order_card = self._build_current_order_card()
        self.payment_summary_card = self._build_payment_summary_card()
        self.update_payment_card = self._build_update_payment_card()
        right_layout.addWidget(self.current_order_card)
        right_layout.addWidget(self.payment_summary_card)
        right_layout.addWidget(self.update_payment_card)
        right_layout.addStretch(1)

        content_row.addWidget(left_panel, stretch=7)
        content_row.addWidget(right_panel, stretch=3)

        root.addWidget(header_card)
        root.addLayout(content_row, stretch=1)

        self.close_button.clicked.connect(self.accept)
        self.orders_tab_button.clicked.connect(lambda: self._show_detail_tab(0))
        self.measurements_tab_button.clicked.connect(lambda: self._show_detail_tab(1))
        self.payments_tab_button.clicked.connect(lambda: self._show_detail_tab(2))
        self.new_order_button.clicked.connect(self._open_new_order_dialog)
        self.orders_table.cellClicked.connect(self._handle_order_row_clicked)
        self.mark_payment_button.clicked.connect(self._mark_payment)
        self.payment_amount_input.textChanged.connect(lambda _value="": self._refresh_mark_payment_button_text())
        self.payment_notes_input.textChanged.connect(self._refresh_mark_payment_button_text)
        self.delivered_button.clicked.connect(self._mark_delivered)
        self.save_measurements_button.clicked.connect(self._save_measurements)
        self._refresh_latest_order_summary()
        apply_widget_translations(self, language_code)
        translate_table_headers(self.orders_table, self.ORDER_HEADERS, language_code)
        translate_table_headers(self.payments_table, self.PAYMENT_HEADERS, language_code)
        translate_table_headers(self.measurements_table, self.MEASUREMENT_HEADERS, language_code)
        install_action_logging(self, screen=self.__class__.__name__)

    def _summary_metric(self, value: str, label: str) -> QWidget:
        wrapper = QWidget()
        wrapper.setFixedHeight(46)
        wrapper.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(2)
        value_label = QLabel(value)
        value_label.setObjectName("DetailMetricValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_widget = QLabel(label)
        label_widget.setObjectName("DetailMetricLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return wrapper

    def _summary_separator(self) -> QFrame:
        separator = QFrame()
        separator.setObjectName("DetailSummarySeparator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedSize(1, 50)
        return separator

    def _initials(self, name: str) -> str:
        parts = [part for part in name.strip().split() if part]
        if not parts:
            return "--"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f"{parts[0][0]}{parts[-1][0]}".upper()

    def _build_order_summaries(self) -> tuple[dict[str, object], ...]:
        summaries: dict[str, dict[str, object]] = {}
        for row in self._order_history:
            summaries.setdefault(
                row.order_id,
                {
                    "order_id": row.order_id,
                    "order_date": row.order_date,
                    "due_date": row.due_date,
                    "total_items": row.order_quantity,
                    "paid_amount": row.paid_amount,
                    "amount": row.order_total,
                    "balance_amount": max(Decimal("0.00"), row.order_total - row.paid_amount),
                    "bill_status": row.bill_status,
                    "status": row.order_status,
                },
            )
        return tuple(summaries.values())

    def _show_detail_tab(self, index: int) -> None:
        log_ui_action(
            self.__class__.__name__,
            "show_detail_tab",
            tab_index=index,
            customer_id=self._customer.customer_id,
        )
        self.content_stack.setCurrentIndex(index)
        self.orders_tab_button.setChecked(index == 0)
        self.measurements_tab_button.setChecked(index == 1)
        self.payments_tab_button.setChecked(index == 2)
        self.save_measurements_button.setVisible(index == 1)

    def _set_order_summary_rows(self) -> None:
        self._order_radio_buttons = []
        if not self._order_summaries:
            self.orders_table.setRowCount(1)
            self.orders_table.setSpan(0, 0, 1, self.orders_table.columnCount())
            empty_item = QTableWidgetItem("No orders found for this customer.")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.orders_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.orders_table.columnCount()):
                self.orders_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.orders_table.setRowCount(len(self._order_summaries))
        radio_group = QButtonGroup(self.orders_table)
        radio_group.setExclusive(True)
        self._order_button_group = radio_group
        for row_index, row in enumerate(self._order_summaries):
            values = (
                "",
                str(row["order_id"]),
                self._format_date(row["order_date"]),  # type: ignore[arg-type]
                str(row["total_items"]),
                self._format_currency(row["paid_amount"]),  # type: ignore[arg-type]
                self._format_currency(row["amount"]),  # type: ignore[arg-type]
                self._format_currency(row["balance_amount"]),  # type: ignore[arg-type]
                str(row["bill_status"]),
                str(row["status"]),
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.orders_table.setItem(row_index, column_index, item)
            radio = QRadioButton()
            radio.setChecked(str(row["order_id"]) == self._selected_order_id)
            radio.toggled.connect(
                lambda checked=False, order_id=str(row["order_id"]): self._select_order(order_id)
                if checked
                else None
            )
            radio.setStyleSheet("margin-left: 7px;")
            radio_group.addButton(radio)
            self._order_radio_buttons.append(radio)
            self.orders_table.setCellWidget(row_index, 0, radio)

    def _set_payment_rows(self) -> None:
        if not self._payment_history:
            self.payments_table.setRowCount(1)
            self.payments_table.setSpan(0, 0, 1, self.payments_table.columnCount())
            empty_item = QTableWidgetItem("No received payment history found for this customer.")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.payments_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.payments_table.columnCount()):
                self.payments_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.payments_table.setRowCount(len(self._payment_history))
        for row_index, row in enumerate(self._payment_history):
            values = (
                row.order_id,
                self._format_date(row.payment_date),
                self._format_currency(row.paid_amount),
                row.notes,
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.payments_table.setItem(row_index, column_index, item)

    def _set_measurement_rows(self) -> None:
        if not self._measurement_rows:
            self.measurements_table.setRowCount(1)
            self.measurements_table.setSpan(0, 0, 1, self.measurements_table.columnCount())
            empty_item = QTableWidgetItem("No measurements found for this customer.")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.measurements_table.setItem(0, 0, empty_item)
            for column_index in range(1, self.measurements_table.columnCount()):
                self.measurements_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self.measurements_table.setRowCount(len(self._measurement_rows))
        self.measurements_table.clearSpans()
        for row_index, row in enumerate(self._measurement_rows):
            values = (
                row.item_name,
                row.measurements,
                self._format_weight(row.weight),
                self._format_date(row.measurement_date),
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if column_index in {1, 2}:
                    flags |= Qt.ItemFlag.ItemIsEditable
                item.setFlags(flags)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.measurements_table.setItem(row_index, column_index, item)

    def _handle_order_row_clicked(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._order_summaries):
            return
        self._select_order(str(self._order_summaries[row]["order_id"]))

    def _select_order(self, order_id: str) -> None:
        log_ui_action(
            self.__class__.__name__,
            "select_order",
            order_id=order_id,
            customer_id=self._customer.customer_id,
        )
        self._selected_order_id = order_id
        for row_index, row in enumerate(self._order_summaries):
            if row_index < len(self._order_radio_buttons):
                self._order_radio_buttons[row_index].setChecked(str(row["order_id"]) == order_id)
        self._refresh_latest_order_summary()

    def _selected_order_summary(self) -> dict[str, object] | None:
        for row in self._order_summaries:
            if str(row["order_id"]) == self._selected_order_id:
                return row
        return self._order_summaries[0] if self._order_summaries else None

    def _build_current_order_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("DetailSideCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        title = QLabel("Current Order")
        title.setObjectName("DetailSideTitle")
        layout.addWidget(title)
        self.current_order_id = self._summary_line(layout, "Order ID")
        self.current_total_items = self._summary_line(layout, "Total Items")
        self.current_bill_status = self._summary_line(layout, "Bill Status")
        self.current_order_status = self._summary_line(layout, "Status")
        self.current_delivery_date = self._summary_line(layout, "Delivery Date")
        return card

    def _build_payment_summary_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("DetailSideCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        title = QLabel("Payment Summary")
        title.setObjectName("DetailSideTitle")
        layout.addWidget(title)
        self.payment_total_amount = self._summary_line(layout, "Total Amount")
        self.payment_paid_amount = self._summary_line(layout, "Paid Amount", tone="success")
        self.payment_balance_amount = self._summary_line(layout, "Balance Amount", tone="danger")
        self.payment_progress = QFrame()
        self.payment_progress.setObjectName("PaymentProgressTrack")
        self.payment_progress.setFixedWidth(230)
        self.payment_progress.setFixedHeight(7)
        self.payment_progress_fill = QFrame(self.payment_progress)
        self.payment_progress_fill.setObjectName("PaymentProgressFill")
        self.payment_progress_fill.setFixedHeight(7)
        layout.addWidget(self.payment_progress)
        self.payment_percent = QLabel("0% Paid")
        self.payment_percent.setObjectName("PaymentPercent")
        self.payment_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.payment_percent)
        return card

    def _build_update_payment_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("DetailSideCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)
        title = QLabel("Update Payment")
        title.setObjectName("DetailSideTitle")
        layout.addWidget(title)

        amount_label = QLabel("Amount Received")
        amount_label.setObjectName("DetailSideLabel")
        self.payment_amount_input = QLineEdit()
        self.payment_amount_input.setObjectName("DetailInput")
        self.payment_amount_input.setPlaceholderText("Enter amount")
        method_label = QLabel("Payment Method")
        method_label.setObjectName("DetailSideLabel")
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.setObjectName("DetailInput")
        self.payment_method_combo.addItems(("Cash", "UPI", "Card", "Bank Transfer", "Other"))
        notes_label = QLabel("Notes (Optional)")
        notes_label.setObjectName("DetailSideLabel")
        self.payment_notes_input = QPlainTextEdit()
        self.payment_notes_input.setObjectName("DetailNotes")
        self.payment_notes_input.setPlaceholderText("Add a note")
        self.payment_notes_input.setFixedHeight(40)
        self.mark_payment_button = QPushButton("Mark Payment")
        self.mark_payment_button.setObjectName("DetailPrimaryButton")
        self.print_receipt_button = QPushButton("Print Receipt")
        self.print_receipt_button.setObjectName("DetailOutlineButton")
        self.delivered_button = QPushButton("Delivered")
        self.delivered_button.setObjectName("DetailPrimaryButton")
        self.delivered_button.hide()
        self.payment_feedback = QLabel("")
        self.payment_feedback.setObjectName("DetailFeedback")
        self.payment_feedback.setWordWrap(True)
        self.payment_feedback.hide()

        self._payment_form_widgets = (
            amount_label,
            self.payment_amount_input,
            method_label,
            self.payment_method_combo,
            notes_label,
            self.payment_notes_input,
            self.mark_payment_button,
            self.print_receipt_button,
        )

        layout.addWidget(amount_label)
        layout.addWidget(self.payment_amount_input)
        layout.addWidget(method_label)
        layout.addWidget(self.payment_method_combo)
        layout.addWidget(notes_label)
        layout.addWidget(self.payment_notes_input)
        layout.addWidget(self.mark_payment_button)
        layout.addWidget(self.print_receipt_button)
        layout.addWidget(self.delivered_button)
        layout.addWidget(self.payment_feedback)
        return card

    def _mark_payment(self) -> None:
        log_ui_action(
            self.__class__.__name__,
            "mark_payment",
            order_id=self._selected_order_id or "",
            customer_id=self._customer.customer_id,
        )
        if not self._selected_order_id:
            self._set_payment_feedback("Select an order before marking payment.", tone="error")
            return
        raw_amount = self.payment_amount_input.text().replace(",", "").strip()
        notes = self.payment_notes_input.toPlainText()
        normalized_notes = notes.strip()
        try:
            amount = (
                Decimal("0.00")
                if not raw_amount
                and normalized_notes
                else Decimal(raw_amount).quantize(Decimal("0.01"))
            )
        except Exception:
            self._set_payment_feedback("Enter a valid payment amount.", tone="error")
            return
        try:
            self._operations_service.add_payment_for_order(
                store_id=self._store_id,
                customer_id=self._customer.customer_id,
                order_id=self._selected_order_id,
                paid_amount=amount,
                payment_method=self.payment_method_combo.currentText(),
                notes=notes,
            )
        except ValueError as exc:
            self._set_payment_feedback(str(exc), tone="error")
            return
        self.payment_amount_input.clear()
        self.payment_notes_input.clear()
        self._set_payment_feedback("Payment recorded.", tone="success")
        self._reload_customer_detail_data()

    def _mark_delivered(self) -> None:
        log_ui_action(
            self.__class__.__name__,
            "mark_delivered",
            order_id=self._selected_order_id or "",
            customer_id=self._customer.customer_id,
        )
        if not self._selected_order_id:
            self._set_payment_feedback("Select an order before marking delivery.", tone="error")
            return
        try:
            self._operations_service.mark_order_delivered_for_store(
                store_id=self._store_id,
                customer_id=self._customer.customer_id,
                order_id=self._selected_order_id,
            )
        except ValueError as exc:
            self._set_payment_feedback(str(exc), tone="error")
            return
        self._set_payment_feedback("Order marked delivered.", tone="success")
        self._reload_customer_detail_data()

    def _open_new_order_dialog(self) -> None:
        log_ui_action(
            self.__class__.__name__,
            "open_new_order_dialog",
            customer_id=self._customer.customer_id,
        )
        item_rows = self._operations_service.list_items(store_id=self._store_id)
        if not item_rows:
            self._set_payment_feedback("Create store items before creating an order.", tone="error")
            return
        dialog = CustomerOrderEntryDialog(
            item_rows=item_rows,
            created_by_name=self._created_by_name,
            customer=self._customer,
            measurement_rows=self._measurement_rows,
            language_code=self._language_code,
            parent=self,
        )
        while dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.payload()
            order_items = payload["items"]
            if not isinstance(order_items, tuple) or not order_items:
                dialog.set_feedback("Add at least one order item before saving.", tone="error")
                continue
            try:
                self._operations_service.create_order_for_customer(
                    store_id=self._store_id,
                    customer_id=self._customer.customer_id,
                    order=CustomerOrderCreateInput(
                        title=self._default_order_title(order_items),
                        created_by=str(payload["created_by"]),
                        due_on=payload["due_on"],  # type: ignore[arg-type]
                        priority=str(payload["priority"]),
                        status=str(payload["order_status"]),
                        paid_amount=payload["paid_amount"],  # type: ignore[arg-type]
                        items=order_items,
                        weight=payload["weight"],  # type: ignore[arg-type]
                    ),
                )
            except ValueError as exc:
                dialog.set_feedback(str(exc), tone="error")
                continue
            self._set_payment_feedback("Order created.", tone="success")
            self._reload_customer_detail_data()
            self._show_detail_tab(0)
            break

    def _default_order_title(self, items: tuple[OrderItemCreateInput, ...]) -> str:
        if len(items) == 1:
            return items[0].item_name
        return " + ".join(item.item_name for item in items[:3])

    def _save_measurements(self) -> None:
        log_ui_action(
            self.__class__.__name__,
            "save_measurements",
            customer_id=self._customer.customer_id,
            measurement_count=len(self._measurement_rows),
        )
        if not self._measurement_rows:
            return
        try:
            for row_index, measurement in enumerate(self._measurement_rows):
                measurement_item = self.measurements_table.item(row_index, 1)
                if measurement_item is None:
                    continue
                weight_item = self.measurements_table.item(row_index, 2)
                self._operations_service.save_measurement_for_store(
                    store_id=self._store_id,
                    customer_id=self._customer.customer_id,
                    item_id=measurement.item_id,
                    item_name=measurement.item_name,
                    measurements=measurement_item.text(),
                    measurement_id=measurement.measurement_id,
                    weight=self._parse_optional_weight(
                        weight_item.text() if weight_item is not None else ""
                    ),
                )
        except ValueError as exc:
            self._set_payment_feedback(str(exc), tone="error")
            return
        self._set_payment_feedback("Measurements saved.", tone="success")
        self._reload_customer_detail_data()
        self._show_detail_tab(1)

    def _reload_customer_detail_data(self) -> None:
        customer = self._operations_service.get_customer_for_store(
            store_id=self._store_id,
            customer_id=self._customer.customer_id,
        )
        if customer is not None:
            self._customer = customer
        self._order_history = self._operations_service.list_customer_order_history_for_store(
            store_id=self._store_id,
            customer_id=self._customer.customer_id,
        )
        self._payment_history = self._operations_service.list_payment_history_for_store(
            store_id=self._store_id,
            customer_id=self._customer.customer_id,
        )
        self._measurement_rows = self._operations_service.list_measurements_for_customer(
            customer_id=self._customer.customer_id,
            store_id=self._store_id,
        )
        previous_order_id = self._selected_order_id
        self._order_summaries = self._build_order_summaries()
        available_order_ids = {str(row["order_id"]) for row in self._order_summaries}
        self._selected_order_id = (
            previous_order_id
            if previous_order_id in available_order_ids
            else str(self._order_summaries[0]["order_id"])
            if self._order_summaries
            else ""
        )
        self._set_order_summary_rows()
        self._set_payment_rows()
        self._set_measurement_rows()
        self._refresh_latest_order_summary()

    def _set_payment_feedback(self, message: str, *, tone: str) -> None:
        self.payment_feedback.setText(message)
        self.payment_feedback.setVisible(bool(message))
        self.payment_feedback.setProperty("tone", tone)
        self.payment_feedback.style().unpolish(self.payment_feedback)
        self.payment_feedback.style().polish(self.payment_feedback)
        self.payment_feedback.update()

    def _summary_line(self, layout: QVBoxLayout, label: str, *, tone: str = "") -> QLabel:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label_widget = QLabel(label)
        label_widget.setObjectName("DetailSideLabel")
        value_widget = QLabel("--")
        value_widget.setObjectName("DetailSideValue")
        if tone:
            value_widget.setProperty("tone", tone)
        value_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label_widget, stretch=1)
        row.addWidget(value_widget)
        layout.addLayout(row)
        return value_widget

    def _refresh_latest_order_summary(self) -> None:
        summary = self._selected_order_summary()
        if summary is None:
            return
        amount = summary["amount"]  # type: ignore[assignment]
        paid_amount = summary["paid_amount"]  # type: ignore[assignment]
        balance_amount = summary["balance_amount"]  # type: ignore[assignment]
        percent = 0
        if isinstance(amount, Decimal) and amount > Decimal("0.00") and isinstance(paid_amount, Decimal):
            percent = int(min(100, (paid_amount / amount) * Decimal("100")))
        self.current_order_id.setText(str(summary["order_id"]))
        self.current_total_items.setText(str(summary["total_items"]))
        self.current_bill_status.setText(str(summary["bill_status"]))
        self.current_order_status.setText(str(summary["status"]))
        self.current_delivery_date.setText(self._format_date(summary["due_date"]))  # type: ignore[arg-type]
        self.payment_total_amount.setText(self._format_currency(amount))  # type: ignore[arg-type]
        self.payment_paid_amount.setText(self._format_currency(paid_amount))  # type: ignore[arg-type]
        self.payment_balance_amount.setText(self._format_currency(balance_amount))  # type: ignore[arg-type]
        self.payment_percent.setText(f"{percent}% Paid")
        self.payment_progress_fill.setFixedWidth(max(0, int(self.payment_progress.width() * percent / 100)))
        self._refresh_payment_action_card(summary)

    def _refresh_payment_action_card(self, summary: dict[str, object]) -> None:
        balance_amount = summary["balance_amount"]
        is_paid = isinstance(balance_amount, Decimal) and balance_amount <= Decimal("0.00")
        for widget in self._payment_form_widgets:
            widget.setVisible(not is_paid)
        self.delivered_button.setVisible(is_paid)
        self.delivered_button.setEnabled(str(summary["status"]) != "DELIVERED")
        self._refresh_mark_payment_button_text()

    def _refresh_mark_payment_button_text(self) -> None:
        summary = self._selected_order_summary()
        if summary is None:
            self.mark_payment_button.setText("Mark Payment")
            return
        balance_amount = summary["balance_amount"]
        if not isinstance(balance_amount, Decimal):
            self.mark_payment_button.setText("Mark Payment")
            return

        raw_amount = self.payment_amount_input.text().replace(",", "").strip()
        notes = self.payment_notes_input.toPlainText().strip()
        try:
            amount = Decimal("0.00") if not raw_amount and notes else Decimal(raw_amount).quantize(Decimal("0.01"))
        except Exception:
            amount = None

        should_deliver_without_full_payment = (
            str(summary["status"]) == "READY"
            and str(summary["bill_status"]) == "PARTPAID"
            and amount is not None
            and amount < balance_amount
            and bool(notes)
        )
        self.mark_payment_button.setText(
            "Deliver-WP" if should_deliver_without_full_payment else "Mark Payment"
        )

    def _format_date(self, value: datetime | None) -> str:
        if value is None:
            return "--"
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d")

    def _format_currency(self, value: Decimal) -> str:
        return f"INR {value:,.2f}"

    def _format_weight(self, value: Decimal | None) -> str:
        if value is None:
            return ""
        return f"{value:,.2f}"

    def _parse_optional_weight(self, value: str) -> Decimal | None:
        normalized_value = value.strip().replace(",", "")
        if not normalized_value or normalized_value == "--":
            return None
        try:
            parsed = Decimal(normalized_value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Enter a valid customer weight.") from exc
        if parsed < Decimal("0.00"):
            raise ValueError("Customer weight cannot be negative.")
        return parsed.quantize(Decimal("0.01"))

    def _apply_dialog_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #ffffff;
                color: #111827;
            }
            QFrame#DetailSummaryBar {
                background-color: #ffffff;
                border: none;
                border-bottom: 1px solid #edf0f7;
            }
            QLabel#DetailAvatar {
                border-radius: 21px;
                background-color: #dedbff;
                color: #4338ca;
                font-size: 10pt;
                font-weight: 700;
            }
            QLabel#DetailTitle {
                color: #111827;
                font-size: 14pt;
                font-weight: 700;
            }
            QLabel#DetailMeta {
                color: #667085;
                font-size: 7pt;
            }
            QFrame#DetailSummarySeparator {
                background-color: #edf0f7;
                border: none;
            }
            QLabel#DetailMetricValue {
                color: #111827;
                font-size: 9pt;
                font-weight: 700;
            }
            QLabel#DetailMetricLabel {
                color: #8b95ad;
                font-size: 6pt;
                font-weight: 700;
            }
            QLabel#DetailSectionTitle {
                color: #111827;
                font-size: 14pt;
                font-weight: 700;
            }
            QLabel#DetailCount {
                color: #30384d;
                font-size: 10pt;
                font-weight: 700;
            }
            QPushButton#DetailTabButton {
                min-height: 28px;
                min-width: 84px;
                border: 1px solid #dfe3ec;
                border-radius: 5px;
                background-color: #ffffff;
                color: #30384d;
                font-size: 8pt;
                font-weight: 700;
                padding: 0 10px;
            }
            QPushButton#DetailTabButton:checked {
                background-color: #5c57e6;
                border-color: #5c57e6;
                color: #ffffff;
            }
            QFrame#DetailSideCard {
                background-color: #ffffff;
                border: 1px solid #e7eaf2;
                border-radius: 6px;
            }
            QLabel#DetailSideTitle {
                color: #172554;
                font-size: 10pt;
                font-weight: 700;
            }
            QLabel#DetailSideLabel {
                color: #34405a;
                font-size: 7pt;
            }
            QLabel#DetailSideValue {
                color: #111827;
                font-size: 8pt;
                font-weight: 700;
            }
            QLabel#DetailSideValue[tone="success"] {
                color: #16a34a;
            }
            QLabel#DetailSideValue[tone="danger"] {
                color: #ef4444;
            }
            QFrame#PaymentProgressTrack {
                background-color: #e5e7eb;
                border-radius: 4px;
            }
            QFrame#PaymentProgressFill {
                background-color: #16a34a;
                border-radius: 4px;
            }
            QLabel#PaymentPercent {
                color: #16a34a;
                font-size: 8pt;
                font-weight: 700;
            }
            QLineEdit#DetailInput,
            QComboBox#DetailInput {
                min-height: 24px;
                border: 1px solid #dfe3ec;
                border-radius: 5px;
                background-color: #ffffff;
                color: #111827;
                padding: 0 8px;
                font-size: 8pt;
            }
            QPlainTextEdit#DetailNotes {
                border: 1px solid #dfe3ec;
                border-radius: 5px;
                background-color: #ffffff;
                color: #111827;
                padding: 4px 6px;
                font-size: 8pt;
            }
            QPushButton#DetailPrimaryButton {
                min-height: 28px;
                border: 1px solid #09213f;
                border-radius: 5px;
                background-color: #09213f;
                color: #ffffff;
                font-size: 8pt;
                font-weight: 700;
                padding: 0 10px;
            }
            QPushButton#DetailOutlineButton {
                min-height: 28px;
                border: 1px solid #dfe3ec;
                border-radius: 5px;
                background-color: #ffffff;
                color: #09213f;
                font-size: 8pt;
                font-weight: 700;
                padding: 0 10px;
            }
            QLabel#DetailFeedback {
                font-size: 7pt;
                font-weight: 700;
            }
            QLabel#DetailFeedback[tone="success"] {
                color: #027a48;
            }
            QLabel#DetailFeedback[tone="error"] {
                color: #b42318;
            }
            QPushButton#DialogSecondaryButton {
                min-height: 30px;
                border: 1px solid #dfe3ec;
                border-radius: 6px;
                background-color: #ffffff;
                color: #30384d;
                font-size: 8pt;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton#DialogSecondaryButton:hover {
                background-color: #f8fafc;
            }
            QTableWidget#DialogItemsTable {
                background-color: #ffffff;
                alternate-background-color: #fafbff;
                border: 1px solid #e7eaf2;
                border-radius: 8px;
                color: #111827;
                outline: none;
            }
            QTableWidget#DialogItemsTable::item {
                padding: 2px 5px;
                border-bottom: 1px solid #edf0f7;
                font-size: 7pt;
            }
            QTableWidget#DialogItemsTable::item:selected {
                background-color: #eef2ff;
                color: #111827;
            }
            QTableWidget#DialogItemsTable QRadioButton {
                background-color: transparent;
            }
            QTableWidget#DialogItemsTable QHeaderView::section {
                background-color: #f2f1fb;
                color: #20263a;
                border: none;
                border-bottom: 1px solid #e3e6f0;
                padding: 3px 5px;
                font-size: 8pt;
                font-weight: 700;
            }
            """
        )


def _filter_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FilterLabel")
    return label


class StoreManagerCustomerDashboardScreen(QWidget):
    TABLE_HEADERS = ("Name", "Phone", "Last Order", "Balance")
    FUTURE_HEADERS = ("Customer Name", "Due Date", "Item")
    CUSTOMER_PAGE_SIZE = 8
    CUSTOMER_VISIBLE_ROWS = CUSTOMER_PAGE_SIZE
    FUTURE_VISIBLE_ROWS = 10

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
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_search)
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
        future_title = QLabel("Ordered Items")
        future_title.setObjectName("SectionTitle")
        future_copy = QLabel("Item-wise customer orders with NEW status rows shown first.")
        future_copy.setObjectName("SectionCopy")
        future_copy.setWordWrap(True)
        future_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        future_layout.addWidget(future_title)
        future_layout.addWidget(future_copy)
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(10)
        filter_row.addWidget(_filter_label("Due Date"))
        self.due_date_filter = QComboBox()
        self.due_date_filter.setObjectName("DueDateFilter")
        self.due_date_filter.setMinimumHeight(36)
        filter_row.addWidget(self.due_date_filter, stretch=1)
        self.ordered_items_count_label = QLabel("Total Items: 0")
        self.ordered_items_count_label.setObjectName("OrderedItemsCount")
        self.ordered_items_count_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        filter_row.addWidget(self.ordered_items_count_label)
        filter_row.addStretch(1)
        future_layout.addLayout(filter_row)
        self.future_table = QTableWidget(0, len(self.FUTURE_HEADERS))
        self.future_table.setObjectName("DashboardTable")
        self.future_table.setProperty("managerTable", True)
        self.future_table.setProperty("orderedItemsTable", True)
        self.future_table.setHorizontalHeaderLabels(list(self.FUTURE_HEADERS))
        self.future_table.setAlternatingRowColors(True)
        self.future_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.future_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.future_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.future_table.setShowGrid(False)
        self.future_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.future_table.verticalHeader().setVisible(False)
        self.future_table.verticalHeader().setDefaultSectionSize(34)
        self.future_table.horizontalHeader().setStretchLastSection(False)
        self.future_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.future_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.future_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.future_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        future_layout.addWidget(self.future_table)
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
        self.customer_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.customer_table.verticalHeader().setVisible(False)
        self.customer_table.verticalHeader().setDefaultSectionSize(36)
        self.customer_table.horizontalHeader().setStretchLastSection(True)
        self.customer_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        for column_index in range(len(self.TABLE_HEADERS)):
            self.customer_table.horizontalHeader().setSectionResizeMode(
                column_index,
                QHeaderView.ResizeMode.Stretch,
            )
        pagination_row = QHBoxLayout()
        pagination_row.setContentsMargins(0, 0, 0, 0)
        pagination_row.setSpacing(6)
        self.pagination_label = QLabel("")
        self.pagination_label.setObjectName("PaginationLabel")
        self.previous_page_button = QPushButton("Previous")
        self.previous_page_button.setObjectName("SecondaryButton")
        self.previous_page_button.setProperty("paginationButton", True)
        self.previous_page_button.setMinimumHeight(28)
        self.previous_page_button.setMinimumWidth(72)
        self.page_buttons_container = QWidget()
        page_buttons_layout = QHBoxLayout(self.page_buttons_container)
        page_buttons_layout.setContentsMargins(0, 0, 0, 0)
        page_buttons_layout.setSpacing(6)
        self._page_buttons_layout = page_buttons_layout
        self._page_buttons: list[QPushButton] = []
        self.next_page_button = QPushButton("Next")
        self.next_page_button.setObjectName("SecondaryButton")
        self.next_page_button.setProperty("paginationButton", True)
        self.next_page_button.setMinimumHeight(28)
        self.next_page_button.setMinimumWidth(72)
        pagination_row.addWidget(self.pagination_label, stretch=1)
        pagination_row.addWidget(self.previous_page_button)
        pagination_row.addWidget(self.page_buttons_container)
        pagination_row.addWidget(self.next_page_button)
        customer_layout.addWidget(search_title)
        customer_layout.addLayout(search_row)
        customer_layout.addWidget(search_copy)
        customer_layout.addWidget(self.feedback_label)
        customer_layout.addWidget(self.customer_table)
        customer_layout.addStretch(1)
        customer_layout.addLayout(pagination_row)

        layout.addWidget(customer_card, 0, 0)
        layout.addWidget(future_card, 0, 1)
        root.addLayout(layout, stretch=1)

        self.search_input.returnPressed.connect(self._apply_search)
        self.search_input.textChanged.connect(self._handle_search_text_changed)
        self.search_button.clicked.connect(self._apply_search)
        self.add_customer_button.clicked.connect(self._open_add_customer_dialog)
        self.customer_table.cellDoubleClicked.connect(self._open_customer_details_dialog)
        self.previous_page_button.clicked.connect(self._show_previous_page)
        self.next_page_button.clicked.connect(self._show_next_page)
        self.due_date_filter.currentTextChanged.connect(self._apply_due_date_filter)
        _apply_compact_table_style(self.future_table, row_height=28, embedded=True)
        _apply_compact_table_style(self.customer_table, row_height=28, embedded=True)
        self.clear_context()
        install_action_logging(self, screen=self.__class__.__name__, context=self._log_context)

    def set_context(
        self,
        *,
        current_user_id: str | None,
        store_context: StoreDashboardContext,
    ) -> None:
        self._current_user_id = current_user_id
        self._store_context = store_context
        self._set_feedback("", tone="success")
        self.refresh_language()
        self.refresh_data()

    def clear_context(self) -> None:
        self._search_timer.stop()
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
        self.due_date_filter.blockSignals(True)
        self.due_date_filter.clear()
        self.due_date_filter.addItem(tr("All Due Dates", self._language_code()))
        self.due_date_filter.blockSignals(False)
        self._set_ordered_items_count(0)
        self.search_input.clear()
        self.search_input.setEnabled(False)
        self.search_button.setEnabled(False)
        self.add_customer_button.setEnabled(True)
        self.previous_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)
        self.pagination_label.setText("")
        self._set_feedback("", tone="success")
        self._set_table_rows(())
        self._set_future_table_rows(())

    def refresh_language(self) -> None:
        language_code = self._language_code()
        apply_widget_translations(self, language_code)
        translate_table_headers(self.customer_table, self.TABLE_HEADERS, language_code)
        translate_table_headers(self.future_table, self.FUTURE_HEADERS, language_code)
        self._set_ordered_items_count(len(self._order_queue_rows))
        self._refresh_pagination_controls()

    def _language_code(self) -> str:
        if self._store_context is None:
            return "en"
        return self._store_context.manager_language_code

    def _log_context(self) -> dict[str, object]:
        return {
            "user_id": self._current_user_id or "",
            "store_id": self._store_context.store_id if self._store_context is not None else "",
        }

    def refresh_data(self) -> None:
        if self._store_context is None:
            self.clear_context()
            return
        self._search_timer.stop()
        self.search_input.setEnabled(True)
        self.search_button.setEnabled(True)
        self._cached_rows_by_id = {}
        self._active_query = ""
        self._database_search_active = False
        self._load_customer_page(page=0)
        self._refresh_order_queue()

    def _apply_search(self) -> None:
        log_ui_action(
            self.__class__.__name__,
            "apply_customer_search",
            query_length=len(self.search_input.text().strip()),
            **self._log_context(),
        )
        self._search_timer.stop()
        if self._store_context is None:
            self._set_table_rows(())
            return
        query = self.search_input.text().strip().lower()
        if not query:
            self._set_feedback("", tone="success")
            self._load_customer_page(page=0)
            return

        self._active_query = query
        self._current_page = 0
        self._database_search_active = True
        self._total_customer_rows = self._operations_service.count_search_customer_summaries_for_store(
            store_id=self._store_context.store_id,
            query=query,
        )
        self._load_database_search_page(page=0)

    def _handle_search_text_changed(self, text: str) -> None:
        self._search_timer.stop()
        if self._store_context is None:
            return
        if not text.strip():
            self._set_feedback("", tone="success")
            self._load_customer_page(page=0)
            return
        self._search_timer.start()

    def _show_previous_page(self) -> None:
        log_ui_action(
            self.__class__.__name__,
            "show_previous_customer_page",
            page=self._current_page,
            **self._log_context(),
        )
        if self._current_page <= 0:
            return
        self._load_active_page(self._current_page - 1)

    def _show_next_page(self) -> None:
        log_ui_action(
            self.__class__.__name__,
            "show_next_customer_page",
            page=self._current_page,
            **self._log_context(),
        )
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
        self._sync_search_feedback()

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
        self._sync_search_feedback()

    def _sync_search_feedback(self) -> None:
        if not self._active_query:
            return
        if self._total_customer_rows == 0:
            self._set_feedback(
                f"No customer found for '{self._active_query}'. Use Add New to create this customer.",
                tone="error",
            )
            return
        self._set_feedback("", tone="success")

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
                empty_text = (
                    f"No customer found for '{self._active_query}'. Use Add New to create this customer."
                    if self._active_query
                    else tr(
                        "No customers found for this store. Use Add New to create the first customer.",
                        self._language_code(),
                    )
                )
                empty_item = QTableWidgetItem(
                    empty_text
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
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
                empty_item = QTableWidgetItem(
                    tr("No store orders available yet.", self._language_code())
                )
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
                    row.due_date.astimezone(timezone.utc).strftime("%Y-%m-%d")
                    if row.due_date is not None
                    else "--",
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
        log_ui_action(
            self.__class__.__name__,
            "open_add_customer_dialog",
            **self._log_context(),
        )
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
            language_code=self._language_code(),
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
                weight=payload["weight"],  # type: ignore[arg-type]
            )
            try:
                log_ui_action(
                    self.__class__.__name__,
                    "create_customer_with_order",
                    item_count=len(order_items),
                    **self._log_context(),
                )
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
            self.refresh_data()
            self.search_input.setText(str(payload["full_name"]))
            self._apply_search()
            break

    def _open_customer_details_dialog(self, row: int, _column: int) -> None:
        log_ui_action(
            self.__class__.__name__,
            "open_customer_details_dialog",
            row=row,
            **self._log_context(),
        )
        if self._store_context is None:
            return
        if row < 0 or row >= len(self._visible_customer_rows):
            return
        selected_customer = self._visible_customer_rows[row]
        customer = self._operations_service.get_customer_for_store(
            store_id=self._store_context.store_id,
            customer_id=selected_customer.customer_id,
        )
        if customer is None:
            self._set_feedback("The selected customer could not be found.", tone="error")
            return
        order_history = self._operations_service.list_customer_order_history_for_store(
            store_id=self._store_context.store_id,
            customer_id=selected_customer.customer_id,
        )
        payment_history = self._operations_service.list_payment_history_for_store(
            store_id=self._store_context.store_id,
            customer_id=selected_customer.customer_id,
        )
        measurement_rows = self._operations_service.list_measurements_for_customer(
            customer_id=selected_customer.customer_id,
            store_id=self._store_context.store_id,
        )
        CustomerDetailsDialog(
            customer=customer,
            order_history=order_history,
            payment_history=payment_history,
            measurement_rows=measurement_rows,
            operations_service=self._operations_service,
            store_id=self._store_context.store_id,
            created_by_name=self._user_management_service.display_name_for_user(self._current_user_id)
            if self._current_user_id is not None
            else "Current manager",
            language_code=self._language_code(),
            parent=self,
        ).exec()
        self.refresh_data()

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
        self._refresh_due_date_filter()
        self._apply_due_date_filter()

    def _refresh_due_date_filter(self) -> None:
        current_value = self.due_date_filter.currentText()
        due_dates = sorted(
            {
                row.due_date.astimezone(timezone.utc).strftime("%Y-%m-%d")
                for row in self._order_queue_rows
                if row.due_date is not None
            }
        )
        all_due_dates_label = tr("All Due Dates", self._language_code())
        resolved_value = current_value if current_value in due_dates else all_due_dates_label
        self.due_date_filter.blockSignals(True)
        self.due_date_filter.clear()
        self.due_date_filter.addItems([all_due_dates_label, *due_dates])
        self.due_date_filter.setCurrentText(resolved_value)
        self.due_date_filter.blockSignals(False)

    def _apply_due_date_filter(self) -> None:
        log_ui_action(
            self.__class__.__name__,
            "apply_ordered_items_due_date_filter",
            due_date=self.due_date_filter.currentText(),
            **self._log_context(),
        )
        selected_due_date = self.due_date_filter.currentText()
        if selected_due_date == tr("All Due Dates", self._language_code()):
            rows = self._order_queue_rows
            self._set_future_table_rows(rows)
            self._set_ordered_items_count(len(rows))
            return
        rows = tuple(
            row
            for row in self._order_queue_rows
            if row.due_date is not None
            and row.due_date.astimezone(timezone.utc).strftime("%Y-%m-%d") == selected_due_date
        )
        self._set_future_table_rows(rows)
        self._set_ordered_items_count(len(rows))

    def _set_ordered_items_count(self, count: int) -> None:
        self.ordered_items_count_label.setText(
            f"{tr('Total Items', self._language_code())}: {max(0, count)}"
        )

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
        header_height = table.horizontalHeader().sizeHint().height()
        frame_height = table.frameWidth() * 2
        height = header_height + (table.verticalHeader().defaultSectionSize() * visible_rows) + frame_height
        table.setMinimumHeight(height)
        table.setMaximumHeight(height)

    def _refresh_pagination_controls(self) -> None:
        total_pages = max(
            1,
            (self._total_customer_rows + self.CUSTOMER_PAGE_SIZE - 1) // self.CUSTOMER_PAGE_SIZE,
        )
        current_page = min(self._current_page + 1, total_pages)
        if self._total_customer_rows == 0:
            empty_label = {
                "mr": "0 पैकी 0 ते 0 दाखवत आहे",
                "hi": "0 में से 0 से 0 दिखा रहे हैं",
            }.get(self._language_code(), "Showing 0 to 0 of 0 entries")
            self.pagination_label.setText(empty_label)
        else:
            start = (self._current_page * self.CUSTOMER_PAGE_SIZE) + 1
            end = min(
                start + len(self._visible_customer_rows) - 1,
                self._total_customer_rows,
            )
            label = {
                "mr": f"{self._total_customer_rows} पैकी {start} ते {end} दाखवत आहे",
                "hi": f"{self._total_customer_rows} में से {start} से {end} दिखा रहे हैं",
            }.get(
                self._language_code(),
                f"Showing {start} to {end} of {self._total_customer_rows} entries",
            )
            self.pagination_label.setText(label)
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
            button.setMinimumSize(28, 28)
            button.setMaximumWidth(34)
            button.clicked.connect(
                lambda _checked=False, number=page_number: self._load_active_page(number - 1)
            )
            attach_action_logging(
                button,
                screen=self.__class__.__name__,
                context=self._log_context,
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
            QLabel#PaginationLabel {
                font-size: 7pt;
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
            QPushButton#SecondaryButton[paginationButton="true"] {
                min-height: 28px;
                min-width: 72px;
                border-radius: 4px;
                font-size: 7pt;
                font-weight: 500;
                padding: 0 8px;
            }
            QPushButton#PageButton {
                min-width: 28px;
                min-height: 28px;
                border: 1px solid #dfe3ea;
                border-radius: 0;
                background-color: #ffffff;
                color: #5c67f2;
                font-size: 7pt;
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
                background-color: transparent;
                alternate-background-color: #fbf6ef;
                border: none;
                border-radius: 0;
                color: #071b2c;
                gridline-color: #eadfce;
                outline: none;
            }
            QTableWidget#DashboardTable[managerTable="true"] QWidget {
                background-color: transparent;
            }
            QTableWidget#DashboardTable[managerTable="true"] QAbstractScrollArea {
                border: none;
                border-radius: 0;
                background-color: transparent;
            }
            QTableWidget#DashboardTable[managerTable="true"]::viewport {
                background-color: transparent;
                border: none;
                border-radius: 0;
            }
            QTableWidget#DashboardTable[managerTable="true"] QScrollBar:vertical,
            QTableWidget#DashboardTable[managerTable="true"] QScrollBar:horizontal {
                background-color: #f3ece4;
                border: none;
                width: 8px;
                height: 8px;
            }
            QTableWidget#DashboardTable[managerTable="true"] QScrollBar::handle:vertical,
            QTableWidget#DashboardTable[managerTable="true"] QScrollBar::handle:horizontal {
                background-color: #cdbda9;
                border-radius: 4px;
                min-height: 24px;
                min-width: 24px;
            }
            QTableWidget#DashboardTable[managerTable="true"] QScrollBar::add-line:vertical,
            QTableWidget#DashboardTable[managerTable="true"] QScrollBar::sub-line:vertical,
            QTableWidget#DashboardTable[managerTable="true"] QScrollBar::add-line:horizontal,
            QTableWidget#DashboardTable[managerTable="true"] QScrollBar::sub-line:horizontal {
                width: 0;
                height: 0;
                border: none;
                background-color: transparent;
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
            QTableWidget#DashboardTable[orderedItemsTable="true"] {
                font-size: 8pt;
            }
            QTableWidget#DashboardTable[orderedItemsTable="true"] QHeaderView::section {
                font-size: 10pt;
                font-weight: 700;
            }
            QLabel#FilterLabel {
                color: #3d3025;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#OrderedItemsCount {
                color: #3d3025;
                font-size: 10pt;
                font-weight: 700;
                padding-left: 8px;
            }
            QComboBox#DueDateFilter {
                min-height: 34px;
                padding: 0 10px;
                border: 1px solid #cbb9a3;
                border-radius: 10px;
                background-color: #fffdfa;
                color: #1f2933;
            }
            """
        )
