from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func, inspect, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class CustomerModel(Base):
    __tablename__ = "ops_customers"

    customer_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    store_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    mobile: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(240), nullable=False)
    is_whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_billing: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    received_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    balance_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    orders: Mapped[list["OrderModel"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class OrderModel(Base):
    __tablename__ = "ops_orders"

    order_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("ops_customers.customer_id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    order_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    bill_status: Mapped[str] = mapped_column(String(40), nullable=False, default="UNPAID")
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    due_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[str] = mapped_column(String(40), nullable=False, default="Medium")
    created_by: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    customer: Mapped[CustomerModel] = relationship(back_populates="orders")
    items: Mapped[list["OrderItemModel"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["PaymentModel"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItemModel(Base):
    __tablename__ = "ops_order_items"

    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("ops_orders.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    measurement_id: Mapped[int | None] = mapped_column(
        ForeignKey("ops_measurements.measurement_id", ondelete="SET NULL"),
        nullable=True,
    )
    measurements: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="NEW")
    assigned_worker_id: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    assigned_worker_name: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    assigned_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(150), nullable=False, default="")

    order: Mapped[OrderModel] = relationship(back_populates="items")
    measurement: Mapped["MeasurementModel | None"] = relationship("MeasurementModel")


class ItemModel(Base):
    __tablename__ = "ops_items"

    item_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(160), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    making_charges: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaymentModel(Base):
    __tablename__ = "ops_payments"

    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("ops_orders.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("ops_customers.customer_id", ondelete="CASCADE"),
        nullable=False,
    )
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    payment_method: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    notes: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    order: Mapped[OrderModel] = relationship(back_populates="payments")


class MeasurementModel(Base):
    __tablename__ = "ops_measurements"

    measurement_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("ops_customers.customer_id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(160), nullable=False)
    measurements: Mapped[str] = mapped_column(String(240), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    measurement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class CustomerRow:
    customer_id: str
    store_id: str | None
    full_name: str
    mobile: str
    email: str
    address: str
    is_whatsapp: bool
    created_on: datetime
    total_billing: Decimal
    received_amount: Decimal
    balance_amount: Decimal


@dataclass(frozen=True)
class OrderRow:
    order_id: str
    customer_id: str
    customer_name: str
    title: str
    quantity: int
    order_total: Decimal
    paid_amount: Decimal
    bill_status: str
    status: str
    notes: str
    due_on: datetime | None
    priority: str
    created_by: str
    created_on: datetime
    updated_on: datetime


@dataclass(frozen=True)
class OrderItemRow:
    order_item_id: int
    order_id: str
    item_id: str
    item_name: str
    quantity: int
    measurement_id: int | None
    measurements: str
    rate: Decimal
    line_amount: Decimal
    status: str
    updated_on: datetime
    updated_by: str


@dataclass(frozen=True)
class ItemRow:
    item_id: str
    store_id: str
    item_name: str
    cost: Decimal
    making_charges: Decimal
    created_on: datetime
    updated_on: datetime


@dataclass(frozen=True)
class MeasurementRow:
    measurement_id: int | None
    customer_id: str
    item_id: str
    item_name: str
    measurements: str
    measurement_date: datetime | None
    weight: Decimal | None = None


@dataclass(frozen=True)
class OrderItemCreateInput:
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


@dataclass(frozen=True)
class CustomerOrderCreateInput:
    title: str
    created_by: str
    due_on: datetime | None
    priority: str
    status: str
    paid_amount: Decimal
    items: tuple[OrderItemCreateInput, ...]
    weight: Decimal | None = None


@dataclass(frozen=True)
class CustomerSummaryRow:
    customer_id: str
    full_name: str
    mobile: str
    email: str
    last_order_on: datetime | None
    balance_amount: Decimal


@dataclass(frozen=True)
class OrderQueueRow:
    customer_name: str
    order_date: datetime
    due_date: datetime | None
    priority: str
    item_name: str
    status: str


@dataclass(frozen=True)
class OrderManagementSummaryRow:
    new_hold_items: int
    worker_count: int
    todays_assigned: int
    total_items: int


@dataclass(frozen=True)
class OrderManagementItemRow:
    order_item_id: int
    customer_name: str
    item_id: str
    item_name: str
    item_status: str
    due_date: datetime | None
    priority: str
    status: str
    assigned_worker_id: str
    assigned_worker_name: str


@dataclass(frozen=True)
class WorkerAssignmentSummaryRow:
    worker_id: str
    worker_name: str
    total_assigned_items: int
    inprogress_items: int


@dataclass(frozen=True)
class WorkerPaymentItemRow:
    customer_name: str
    item_name: str
    item_status: str
    worker_id: str
    worker_name: str
    making_charges: Decimal


@dataclass(frozen=True)
class CustomerOrderHistoryRow:
    order_id: str
    title: str
    order_quantity: int
    order_date: datetime
    due_date: datetime | None
    priority: str
    order_status: str
    bill_status: str
    created_by: str
    order_total: Decimal
    paid_amount: Decimal
    item_name: str
    quantity: int
    measurements: str
    item_status: str
    line_amount: Decimal
    updated_on: datetime
    updated_by: str


@dataclass(frozen=True)
class PaymentHistoryRow:
    order_id: str
    payment_date: datetime
    paid_amount: Decimal
    payment_method: str
    notes: str


class OperationsService:
    ORDER_STATUSES = (
        "NEW",
        "WAITING",
        "INPROGRESS",
        "HOLD",
        "READY",
        "DWP",
        "DELIVERED",
        "CANCELED",
        "FULFILLED",
    )

    def __init__(self, *, engine, session_factory: sessionmaker[Session]) -> None:
        self._engine = engine
        self._session_factory = session_factory
        Base.metadata.create_all(bind=self._engine)
        self._ensure_schema_columns()
        self._seed_if_needed()

    def list_customers(self) -> tuple[CustomerRow, ...]:
        with self._session_factory() as session:
            rows = session.scalars(select(CustomerModel).order_by(CustomerModel.full_name.asc())).all()
            return tuple(self._to_customer_row(row) for row in rows)

    def list_orders(self) -> tuple[OrderRow, ...]:
        with self._session_factory() as session:
            rows = session.scalars(select(OrderModel).order_by(OrderModel.updated_on.desc())).all()
            return tuple(self._to_order_row(row) for row in rows)

    def count_customer_summaries_for_store(self, *, store_id: str) -> int:
        normalized_store_id = store_id.strip()
        if not normalized_store_id:
            return 0

        with self._session_factory() as session:
            return int(
                session.scalar(
                    select(func.count()).select_from(CustomerModel).where(
                        CustomerModel.store_id == normalized_store_id
                    )
                )
                or 0
            )

    def list_customer_summaries_for_store(
        self,
        *,
        store_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[CustomerSummaryRow, ...]:
        normalized_store_id = store_id.strip()
        if not normalized_store_id:
            return ()

        with self._session_factory() as session:
            statement = (
                select(CustomerModel)
                .where(CustomerModel.store_id == normalized_store_id)
                .order_by(CustomerModel.full_name.asc())
            )
            if limit is not None:
                statement = statement.limit(max(0, limit)).offset(max(0, offset))
            rows = session.scalars(statement).all()
            return tuple(self._to_customer_summary_row(row) for row in rows)

    def count_search_customer_summaries_for_store(self, *, store_id: str, query: str) -> int:
        normalized_store_id = store_id.strip()
        normalized_query = query.strip().lower()
        if not normalized_store_id:
            return 0
        if not normalized_query:
            return self.count_customer_summaries_for_store(store_id=normalized_store_id)

        with self._session_factory() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(CustomerModel)
                    .where(CustomerModel.store_id == normalized_store_id)
                    .where(self._customer_search_filter(normalized_query))
                )
                or 0
            )

    def search_customer_summaries_for_store(
        self,
        *,
        store_id: str,
        query: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[CustomerSummaryRow, ...]:
        normalized_store_id = store_id.strip()
        normalized_query = query.strip().lower()
        if not normalized_store_id:
            return ()
        if not normalized_query:
            return self.list_customer_summaries_for_store(
                store_id=normalized_store_id,
                limit=limit,
                offset=offset,
            )

        with self._session_factory() as session:
            statement = (
                select(CustomerModel)
                .where(CustomerModel.store_id == normalized_store_id)
                .where(self._customer_search_filter(normalized_query))
                .order_by(CustomerModel.full_name.asc())
            )
            if limit is not None:
                statement = statement.limit(max(0, limit)).offset(max(0, offset))
            rows = session.scalars(statement).all()
            return tuple(self._to_customer_summary_row(row) for row in rows)

    def list_order_queue_for_store(self, *, store_id: str) -> tuple[OrderQueueRow, ...]:
        normalized_store_id = store_id.strip()
        if not normalized_store_id:
            return ()

        with self._session_factory() as session:
            rows = session.execute(
                select(CustomerModel, OrderModel, OrderItemModel)
                .join(OrderModel, OrderModel.customer_id == CustomerModel.customer_id)
                .join(OrderItemModel, OrderItemModel.order_id == OrderModel.order_id)
                .where(CustomerModel.store_id == normalized_store_id)
                .order_by(
                    (OrderModel.status != "NEW").asc(),
                    OrderModel.created_on.desc(),
                    OrderItemModel.order_item_id.asc(),
                )
            ).all()
            return tuple(
                OrderQueueRow(
                    customer_name=customer.full_name,
                    order_date=self._ensure_utc(order.created_on),
                    due_date=self._ensure_optional_utc(order.due_on),
                    priority=order.priority,
                    item_name=item.item_name,
                    status=item.status or order.status,
                )
                for customer, order, item in rows
            )

    def order_management_summary_for_store(
        self,
        *,
        store_id: str,
        worker_count: int,
        due_date: datetime | None = None,
    ) -> OrderManagementSummaryRow:
        normalized_store_id = store_id.strip()
        if not normalized_store_id:
            return OrderManagementSummaryRow(
                new_hold_items=0,
                worker_count=max(0, worker_count),
                todays_assigned=0,
                total_items=0,
            )

        normalized_due_date = self._ensure_optional_utc(due_date)
        today = datetime.now(tz=timezone.utc).date()
        with self._session_factory() as session:
            statement = (
                select(OrderItemModel)
                .join(OrderModel, OrderModel.order_id == OrderItemModel.order_id)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .where(CustomerModel.store_id == normalized_store_id)
                .where(OrderItemModel.status.in_(("NEW", "HOLD", "ASSIGNED")))
            )
            if normalized_due_date is not None:
                start = normalized_due_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                statement = statement.where(OrderModel.due_on >= start, OrderModel.due_on < end)
            rows = session.scalars(statement).all()
            return OrderManagementSummaryRow(
                new_hold_items=sum(1 for row in rows if row.status in {"NEW", "HOLD"}),
                worker_count=max(0, worker_count),
                todays_assigned=sum(
                    1
                    for row in rows
                    if row.assigned_on is not None
                    and self._ensure_utc(row.assigned_on).date() == today
                ),
                total_items=len(rows),
            )

    def list_worker_assignment_summary_for_store(
        self,
        *,
        store_id: str,
    ) -> tuple[WorkerAssignmentSummaryRow, ...]:
        normalized_store_id = store_id.strip()
        if not normalized_store_id:
            return ()

        with self._session_factory() as session:
            rows = session.scalars(
                select(OrderItemModel)
                .join(OrderModel, OrderModel.order_id == OrderItemModel.order_id)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .where(CustomerModel.store_id == normalized_store_id)
                .where(OrderItemModel.assigned_worker_id != "")
            ).all()
            summaries: dict[str, dict[str, object]] = {}
            for row in rows:
                summary = summaries.setdefault(
                    row.assigned_worker_id,
                    {
                        "worker_id": row.assigned_worker_id,
                        "worker_name": row.assigned_worker_name,
                        "total_assigned_items": 0,
                        "inprogress_items": 0,
                    },
                )
                summary["worker_name"] = row.assigned_worker_name
                if row.status == "ASSIGNED":
                    summary["total_assigned_items"] = int(summary["total_assigned_items"]) + 1
                if row.status == "INSTITCHING":
                    summary["inprogress_items"] = int(summary["inprogress_items"]) + 1
            return tuple(
                WorkerAssignmentSummaryRow(
                    worker_id=str(row["worker_id"]),
                    worker_name=str(row["worker_name"]),
                    total_assigned_items=int(row["total_assigned_items"]),
                    inprogress_items=int(row["inprogress_items"]),
                )
                for row in sorted(summaries.values(), key=lambda item: str(item["worker_name"]).lower())
            )

    def list_order_management_items_for_store(
        self,
        *,
        store_id: str,
        due_date: datetime | None = None,
    ) -> tuple[OrderManagementItemRow, ...]:
        normalized_store_id = store_id.strip()
        if not normalized_store_id:
            return ()
        normalized_due_date = self._ensure_optional_utc(due_date)

        with self._session_factory() as session:
            statement = (
                select(OrderModel, OrderItemModel)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .join(OrderItemModel, OrderItemModel.order_id == OrderModel.order_id)
                .where(CustomerModel.store_id == normalized_store_id)
                .where(OrderItemModel.status.in_(("NEW", "HOLD", "ASSIGNED")))
                .order_by(
                    (OrderItemModel.status != "NEW").asc(),
                    OrderModel.due_on.asc(),
                    OrderModel.priority.asc(),
                    OrderItemModel.order_item_id.asc(),
                )
            )
            if normalized_due_date is not None:
                start = normalized_due_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                statement = statement.where(OrderModel.due_on >= start, OrderModel.due_on < end)
            rows = session.execute(statement).all()
            return tuple(
                OrderManagementItemRow(
                    order_item_id=item.order_item_id,
                    customer_name=order.customer.full_name,
                    item_id=item.item_id,
                    item_name=item.item_name,
                    item_status=item.status,
                    due_date=self._ensure_optional_utc(order.due_on),
                    priority=order.priority,
                    status=order.status,
                    assigned_worker_id=item.assigned_worker_id,
                    assigned_worker_name=item.assigned_worker_name,
                )
                for order, item in rows
            )

    def list_work_management_items_for_store(
        self,
        *,
        store_id: str,
        worker_id: str = "",
    ) -> tuple[OrderManagementItemRow, ...]:
        normalized_store_id = store_id.strip()
        normalized_worker_id = worker_id.strip()
        if not normalized_store_id:
            return ()

        with self._session_factory() as session:
            statement = (
                select(OrderModel, OrderItemModel)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .join(OrderItemModel, OrderItemModel.order_id == OrderModel.order_id)
                .where(CustomerModel.store_id == normalized_store_id)
                .where(OrderItemModel.assigned_worker_id != "")
                .order_by(
                    OrderItemModel.assigned_worker_name.asc(),
                    OrderModel.due_on.asc(),
                    OrderModel.priority.asc(),
                    OrderItemModel.order_item_id.asc(),
                )
            )
            if normalized_worker_id:
                statement = statement.where(OrderItemModel.assigned_worker_id == normalized_worker_id)
            rows = session.execute(statement).all()
            return tuple(
                OrderManagementItemRow(
                    order_item_id=item.order_item_id,
                    customer_name=order.customer.full_name,
                    item_id=item.item_id,
                    item_name=item.item_name,
                    item_status=item.status,
                    due_date=self._ensure_optional_utc(order.due_on),
                    priority=order.priority,
                    status=order.status,
                    assigned_worker_id=item.assigned_worker_id,
                    assigned_worker_name=item.assigned_worker_name,
                )
                for order, item in rows
            )

    def list_worker_payment_items_for_store(
        self,
        *,
        store_id: str,
        worker_id: str = "",
    ) -> tuple[WorkerPaymentItemRow, ...]:
        normalized_store_id = store_id.strip()
        normalized_worker_id = worker_id.strip()
        if not normalized_store_id:
            return ()

        with self._session_factory() as session:
            statement = (
                select(OrderModel, OrderItemModel, ItemModel)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .join(OrderItemModel, OrderItemModel.order_id == OrderModel.order_id)
                .join(
                    ItemModel,
                    (ItemModel.store_id == CustomerModel.store_id)
                    & (ItemModel.item_id == OrderItemModel.item_id),
                )
                .where(CustomerModel.store_id == normalized_store_id)
                .where(OrderItemModel.status == "READY")
                .where(OrderItemModel.assigned_worker_id != "")
                .order_by(
                    OrderItemModel.assigned_worker_name.asc(),
                    OrderModel.due_on.asc(),
                    OrderItemModel.order_item_id.asc(),
                )
            )
            if normalized_worker_id:
                statement = statement.where(OrderItemModel.assigned_worker_id == normalized_worker_id)
            rows = session.execute(statement).all()
            return tuple(
                WorkerPaymentItemRow(
                    customer_name=order.customer.full_name,
                    item_name=order_item.item_name,
                    item_status=order_item.status,
                    worker_id=order_item.assigned_worker_id,
                    worker_name=order_item.assigned_worker_name,
                    making_charges=Decimal(item.making_charges).quantize(Decimal("0.01")),
                )
                for order, order_item, item in rows
            )

    def assign_order_item_to_worker(
        self,
        *,
        store_id: str,
        order_item_id: int,
        worker_id: str,
        worker_name: str,
    ) -> None:
        normalized_store_id = store_id.strip()
        normalized_worker_id = worker_id.strip()
        normalized_worker_name = worker_name.strip()
        if not normalized_store_id or order_item_id <= 0 or not normalized_worker_id:
            raise ValueError("Store, order item, and worker are required before assigning work.")

        with self._session_factory() as session:
            order_item = session.scalar(
                select(OrderItemModel)
                .join(OrderModel, OrderModel.order_id == OrderItemModel.order_id)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .where(
                    CustomerModel.store_id == normalized_store_id,
                    OrderItemModel.order_item_id == order_item_id,
                )
            )
            if order_item is None:
                raise ValueError("The selected order item could not be found for this store.")
            now = datetime.now(tz=timezone.utc)
            order_item.assigned_worker_id = normalized_worker_id
            order_item.assigned_worker_name = normalized_worker_name
            order_item.assigned_on = now
            order_item.status = "ASSIGNED"
            order_item.updated_on = now
            session.commit()

    def update_order_item_status_for_store(
        self,
        *,
        store_id: str,
        order_item_id: int,
        status: str,
    ) -> None:
        normalized_store_id = store_id.strip()
        normalized_status = status.strip().upper()
        if not normalized_store_id or order_item_id <= 0:
            raise ValueError("Store and order item are required before updating item status.")
        if normalized_status not in {"INSTITCHING", "READY", "HOLD"}:
            raise ValueError("Item status must be INSTITCHING, READY, or HOLD.")

        with self._session_factory() as session:
            order_item = session.scalar(
                select(OrderItemModel)
                .join(OrderModel, OrderModel.order_id == OrderItemModel.order_id)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .where(
                    CustomerModel.store_id == normalized_store_id,
                    OrderItemModel.order_item_id == order_item_id,
                )
            )
            if order_item is None:
                raise ValueError("The selected order item could not be found for this store.")
            previous_status = order_item.status
            now = datetime.now(tz=timezone.utc)
            order_item.status = normalized_status
            order_item.updated_on = now
            order = order_item.order
            if (
                previous_status == "ASSIGNED"
                and normalized_status == "INSTITCHING"
                and order.status == "NEW"
            ):
                order.status = "INPROGRESS"
                order.updated_on = now
            if order.items and all(item.status == "READY" for item in order.items):
                order.status = "READY"
                order.updated_on = now
            session.commit()

    def list_items(self, *, store_id: str) -> tuple[ItemRow, ...]:
        normalized_store_id = store_id.strip()
        if not normalized_store_id:
            return ()
        with self._session_factory() as session:
            rows = session.scalars(
                select(ItemModel)
                .where(ItemModel.store_id == normalized_store_id)
                .order_by(ItemModel.item_name.asc())
            ).all()
            return tuple(self._to_item_row(row) for row in rows)

    def get_item(self, *, store_id: str, item_id: str) -> ItemRow | None:
        normalized_store_id = store_id.strip()
        normalized_item_id = item_id.strip()
        if not normalized_store_id or not normalized_item_id:
            return None

        with self._session_factory() as session:
            row = session.scalar(
                select(ItemModel).where(
                    ItemModel.store_id == normalized_store_id,
                    ItemModel.item_id == normalized_item_id,
                )
            )
            if row is None:
                return None
            return self._to_item_row(row)

    def create_item(
        self,
        *,
        store_id: str,
        item_name: str,
        cost: Decimal,
        making_charges: Decimal = Decimal("0.00"),
    ) -> str:
        normalized_store_id = store_id.strip()
        normalized_item_name = item_name.strip()
        if not normalized_store_id:
            raise ValueError("Store context is required before creating an item.")
        if not normalized_item_name:
            raise ValueError("Item name is required.")
        if cost < Decimal("0.00"):
            raise ValueError("Item cost cannot be negative.")
        if making_charges < Decimal("0.00"):
            raise ValueError("Making charges cannot be negative.")

        now = datetime.now(tz=timezone.utc)
        item_id = f"ITEM-{now.strftime('%Y%m%d%H%M%S')}-{now.microsecond:06d}"
        normalized_cost = cost.quantize(Decimal("0.01"))
        normalized_making_charges = making_charges.quantize(Decimal("0.01"))
        with self._session_factory() as session:
            existing_item = session.scalar(
                select(ItemModel).where(
                    ItemModel.store_id == normalized_store_id,
                    func.lower(ItemModel.item_name) == normalized_item_name.lower(),
                )
            )
            if existing_item is not None:
                raise ValueError(f"Item '{normalized_item_name}' already exists for this store.")

            item = ItemModel(
                item_id=item_id,
                store_id=normalized_store_id,
                item_name=normalized_item_name,
                cost=normalized_cost,
                making_charges=normalized_making_charges,
                created_on=now,
                updated_on=now,
            )
            session.add(item)
            session.commit()
            return item_id

    def update_item(
        self,
        *,
        store_id: str,
        item_id: str,
        item_name: str,
        cost: Decimal,
        making_charges: Decimal = Decimal("0.00"),
    ) -> None:
        normalized_store_id = store_id.strip()
        normalized_item_id = item_id.strip()
        normalized_item_name = item_name.strip()
        if not normalized_store_id:
            raise ValueError("Store context is required before updating an item.")
        if not normalized_item_id:
            raise ValueError("Item selection is required before updating an item.")
        if not normalized_item_name:
            raise ValueError("Item name is required.")
        if cost < Decimal("0.00"):
            raise ValueError("Item cost cannot be negative.")
        if making_charges < Decimal("0.00"):
            raise ValueError("Making charges cannot be negative.")

        with self._session_factory() as session:
            item = session.scalar(
                select(ItemModel).where(
                    ItemModel.store_id == normalized_store_id,
                    ItemModel.item_id == normalized_item_id,
                )
            )
            if item is None:
                raise ValueError("The selected item could not be found for this store.")

            duplicate_item = session.scalar(
                select(ItemModel).where(
                    ItemModel.store_id == normalized_store_id,
                    func.lower(ItemModel.item_name) == normalized_item_name.lower(),
                    ItemModel.item_id != normalized_item_id,
                )
            )
            if duplicate_item is not None:
                raise ValueError(f"Item '{normalized_item_name}' already exists for this store.")

            item.item_name = normalized_item_name
            item.cost = cost.quantize(Decimal("0.01"))
            item.making_charges = making_charges.quantize(Decimal("0.01"))
            item.updated_on = datetime.now(tz=timezone.utc)
            session.commit()

    def get_customer(self, customer_id: str) -> CustomerRow | None:
        with self._session_factory() as session:
            row = session.get(CustomerModel, customer_id)
            if row is None:
                return None
            return self._to_customer_row(row)

    def get_customer_for_store(self, *, store_id: str, customer_id: str) -> CustomerRow | None:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        if not normalized_store_id or not normalized_customer_id:
            return None
        with self._session_factory() as session:
            row = session.scalar(
                select(CustomerModel).where(
                    CustomerModel.store_id == normalized_store_id,
                    CustomerModel.customer_id == normalized_customer_id,
                )
            )
            if row is None:
                return None
            return self._to_customer_row(row)

    def get_order(self, order_id: str) -> OrderRow | None:
        with self._session_factory() as session:
            row = session.get(OrderModel, order_id)
            if row is None:
                return None
            return self._to_order_row(row)

    def list_orders_for_customer(self, *, store_id: str, customer_id: str) -> tuple[OrderRow, ...]:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        if not normalized_store_id or not normalized_customer_id:
            return ()
        with self._session_factory() as session:
            rows = session.scalars(
                select(OrderModel)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .where(
                    CustomerModel.store_id == normalized_store_id,
                    OrderModel.customer_id == normalized_customer_id,
                )
                .order_by(OrderModel.created_on.desc())
            ).all()
            return tuple(self._to_order_row(row) for row in rows)

    def list_order_items_for_order(self, *, order_id: str) -> tuple[OrderItemRow, ...]:
        normalized_order_id = order_id.strip()
        if not normalized_order_id:
            return ()
        with self._session_factory() as session:
            rows = session.scalars(
                select(OrderItemModel)
                .where(OrderItemModel.order_id == normalized_order_id)
                .order_by(OrderItemModel.order_item_id.asc())
            ).all()
            return tuple(self._to_order_item_row(row) for row in rows)

    def list_measurements_for_customer(
        self,
        *,
        customer_id: str,
        store_id: str | None = None,
    ) -> tuple[MeasurementRow, ...]:
        normalized_customer_id = customer_id.strip()
        if not normalized_customer_id:
            return ()
        normalized_store_id = store_id.strip() if store_id is not None else ""
        with self._session_factory() as session:
            if self._backfill_measurements_for_customer(
                session=session,
                customer_id=normalized_customer_id,
            ):
                session.commit()
            measurement_rows = session.scalars(
                select(MeasurementModel)
                .where(MeasurementModel.customer_id == normalized_customer_id)
                .order_by(MeasurementModel.measurement_date.desc(), MeasurementModel.measurement_id.desc())
            ).all()
            customer_weight = next(
                (
                    Decimal(row.weight).quantize(Decimal("0.01"))
                    for row in measurement_rows
                    if row.weight is not None
                ),
                None,
            )
            measurement_by_item_id: dict[str, MeasurementRow] = {}
            for row in measurement_rows:
                measurement_by_item_id.setdefault(
                    row.item_id,
                    self._to_measurement_row(row, fallback_weight=customer_weight),
                )
            if not normalized_store_id:
                return tuple(measurement_by_item_id.values())

            items = session.scalars(
                select(ItemModel)
                .where(ItemModel.store_id == normalized_store_id)
                .order_by(ItemModel.item_name.asc())
            ).all()
            return tuple(
                measurement_by_item_id.get(
                    item.item_id,
                    MeasurementRow(
                        measurement_id=None,
                        customer_id=normalized_customer_id,
                        item_id=item.item_id,
                        item_name=item.item_name,
                        measurements="",
                        measurement_date=None,
                        weight=customer_weight,
                    ),
                )
                for item in items
            )

    def list_customer_order_history_for_store(
        self,
        *,
        store_id: str,
        customer_id: str,
    ) -> tuple[CustomerOrderHistoryRow, ...]:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        if not normalized_store_id or not normalized_customer_id:
            return ()

        with self._session_factory() as session:
            rows = session.execute(
                select(OrderModel, OrderItemModel)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .join(OrderItemModel, OrderItemModel.order_id == OrderModel.order_id)
                .where(
                    CustomerModel.store_id == normalized_store_id,
                    OrderModel.customer_id == normalized_customer_id,
                )
                .order_by(OrderModel.created_on.desc(), OrderItemModel.order_item_id.asc())
            ).all()
            return tuple(
                CustomerOrderHistoryRow(
                    order_id=order.order_id,
                    title=order.title,
                    order_quantity=max(1, len(order.items)),
                    order_date=self._ensure_utc(order.created_on),
                    due_date=self._ensure_optional_utc(order.due_on),
                    priority=order.priority,
                    order_status=order.status,
                    bill_status=order.bill_status,
                    created_by=order.created_by,
                    order_total=Decimal(order.order_total).quantize(Decimal("0.01")),
                    paid_amount=Decimal(order.paid_amount).quantize(Decimal("0.01")),
                    item_name=item.item_name,
                    quantity=item.quantity,
                    measurements=self._measurement_text_for_item(item),
                    item_status=item.status,
                    line_amount=Decimal(item.line_amount).quantize(Decimal("0.01")),
                    updated_on=self._ensure_utc(item.updated_on),
                    updated_by=item.updated_by,
                )
                for order, item in rows
            )

    def list_payment_history_for_store(
        self,
        *,
        store_id: str,
        customer_id: str,
    ) -> tuple[PaymentHistoryRow, ...]:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        if not normalized_store_id or not normalized_customer_id:
            return ()

        with self._session_factory() as session:
            rows = session.execute(
                select(PaymentModel)
                .join(CustomerModel, CustomerModel.customer_id == PaymentModel.customer_id)
                .where(
                    CustomerModel.store_id == normalized_store_id,
                    PaymentModel.customer_id == normalized_customer_id,
                )
                .order_by(PaymentModel.payment_date.desc(), PaymentModel.payment_id.desc())
            ).scalars().all()
            return tuple(
                PaymentHistoryRow(
                    order_id=row.order_id,
                    payment_date=self._ensure_utc(row.payment_date),
                    paid_amount=Decimal(row.paid_amount).quantize(Decimal("0.01")),
                    payment_method=row.payment_method,
                    notes=row.notes,
                )
                for row in rows
            )

    def create_customer(
        self,
        *,
        full_name: str,
        mobile: str,
        email: str,
        address: str,
    ) -> str:
        now = datetime.now(tz=timezone.utc)
        customer_id = f"CUS-{now.strftime('%Y%m%d%H%M%S')}"
        with self._session_factory() as session:
            customer = CustomerModel(
                customer_id=customer_id,
                full_name=full_name.strip(),
                mobile=mobile.strip(),
                email=email.strip(),
                address=address.strip(),
                created_on=now,
                total_billing=Decimal("0.00"),
                received_amount=Decimal("0.00"),
                balance_amount=Decimal("0.00"),
            )
            session.add(customer)
            session.commit()
            return customer_id

    def create_customer_with_orders(
        self,
        *,
        store_id: str,
        full_name: str,
        mobile: str,
        email: str,
        address: str,
        is_whatsapp: bool,
        orders: list[CustomerOrderCreateInput],
    ) -> str:
        normalized_store_id = store_id.strip()
        normalized_full_name = full_name.strip()
        normalized_mobile = mobile.strip()
        normalized_email = email.strip().lower()
        normalized_address = address.strip()
        if not normalized_store_id:
            raise ValueError("Store context is required before creating a customer.")
        if not normalized_full_name:
            raise ValueError("Full name is required.")
        if not normalized_mobile:
            raise ValueError("Contact number is required.")
        if not normalized_address:
            raise ValueError("Address is required.")
        if not orders:
            raise ValueError("At least one order is required.")

        now = datetime.now(tz=timezone.utc)
        customer_id = f"CUS-{now.strftime('%Y%m%d%H%M%S')}-{now.microsecond:06d}"
        with self._session_factory() as session:
            existing_customer = session.scalar(
                select(CustomerModel).where(
                    CustomerModel.store_id == normalized_store_id,
                    CustomerModel.mobile == normalized_mobile,
                )
            )
            if existing_customer is not None:
                raise ValueError("A customer with this contact number already exists for this store.")

            customer = CustomerModel(
                customer_id=customer_id,
                store_id=normalized_store_id,
                full_name=normalized_full_name,
                mobile=normalized_mobile,
                email=normalized_email,
                address=normalized_address,
                is_whatsapp=is_whatsapp,
                created_on=now,
                total_billing=Decimal("0.00"),
                received_amount=Decimal("0.00"),
                balance_amount=Decimal("0.00"),
            )

            paid_total = Decimal("0.00")
            for index, order_input in enumerate(orders):
                order = self._build_order_from_input(
                    customer_id=customer_id,
                    order_input=order_input,
                    created_on=now + timedelta(microseconds=index),
                    session=session,
                )
                customer.orders.append(order)
                paid_total += order_input.paid_amount

            customer.received_amount = paid_total.quantize(Decimal("0.01"))
            self._recalculate_customer_billing(customer)
            session.add(customer)
            session.commit()
            return customer_id

    def update_customer(
        self,
        *,
        customer_id: str,
        full_name: str,
        mobile: str,
        email: str,
        address: str,
    ) -> None:
        with self._session_factory() as session:
            customer = session.get(CustomerModel, customer_id)
            if customer is None:
                raise ValueError(f"Unknown customer: {customer_id}")

            customer.full_name = full_name.strip()
            customer.mobile = mobile.strip()
            customer.email = email.strip()
            customer.address = address.strip()
            session.commit()

    def create_order_for_customer(
        self,
        *,
        store_id: str,
        customer_id: str,
        order: CustomerOrderCreateInput,
    ) -> str:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        if not normalized_store_id or not normalized_customer_id:
            raise ValueError("Store and customer are required before creating an order.")

        now = datetime.now(tz=timezone.utc)
        with self._session_factory() as session:
            customer = session.scalar(
                select(CustomerModel).where(
                    CustomerModel.store_id == normalized_store_id,
                    CustomerModel.customer_id == normalized_customer_id,
                )
            )
            if customer is None:
                raise ValueError("The selected customer could not be found for this store.")
            created_order = self._build_order_from_input(
                customer_id=normalized_customer_id,
                order_input=order,
                created_on=now,
                session=session,
            )
            customer.orders.append(created_order)
            customer.received_amount = (
                Decimal(customer.received_amount) + order.paid_amount
            ).quantize(Decimal("0.01"))
            self._recalculate_customer_billing(customer)
            session.commit()
            return created_order.order_id

    def create_order(
        self,
        *,
        customer_id: str,
        title: str,
        quantity: int,
        order_total: Decimal,
        status: str,
        notes: str,
    ) -> str:
        if status not in self.ORDER_STATUSES:
            raise ValueError(f"Unsupported order status: {status}")
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if order_total < Decimal("0.00"):
            raise ValueError("Order total cannot be negative.")

        now = datetime.now(tz=timezone.utc)
        order_id = f"ORD-{now.strftime('%Y%m%d%H%M%S')}"
        with self._session_factory() as session:
            customer = session.get(CustomerModel, customer_id)
            if customer is None:
                raise ValueError(f"Unknown customer: {customer_id}")

            order = OrderModel(
                order_id=order_id,
                customer_id=customer_id,
                title=title.strip(),
                quantity=quantity,
                order_total=order_total.quantize(Decimal("0.01")),
                paid_amount=Decimal("0.00"),
                bill_status="UNPAID",
                status=status,
                notes=notes.strip(),
                created_on=now,
                updated_on=now,
            )
            session.add(order)
            session.flush()
            self._recalculate_customer_billing(customer)
            session.commit()
            return order_id

    def update_order(
        self,
        *,
        order_id: str,
        status: str,
        notes: str,
        title: str | None = None,
        quantity: int | None = None,
        order_total: Decimal | None = None,
    ) -> None:
        if status not in self.ORDER_STATUSES:
            raise ValueError(f"Unsupported order status: {status}")

        with self._session_factory() as session:
            order = session.get(OrderModel, order_id)
            if order is None:
                raise ValueError(f"Unknown order: {order_id}")

            if title is not None:
                order.title = title.strip()
            if quantity is not None:
                if quantity <= 0:
                    raise ValueError("Quantity must be greater than zero.")
                order.quantity = quantity
            if order_total is not None:
                if order_total < Decimal("0.00"):
                    raise ValueError("Order total cannot be negative.")
                order.order_total = order_total.quantize(Decimal("0.01"))

            order.status = status
            order.bill_status = self._bill_status_for_amounts(
                Decimal(order.order_total),
                Decimal(order.paid_amount),
            )
            order.notes = notes.strip()
            order.updated_on = datetime.now(tz=timezone.utc)
            self._recalculate_customer_billing(order.customer)
            session.commit()

    def update_received_amount(self, *, customer_id: str, received_amount: Decimal) -> None:
        if received_amount < Decimal("0.00"):
            raise ValueError("Received amount cannot be negative.")

        with self._session_factory() as session:
            customer = session.get(CustomerModel, customer_id)
            if customer is None:
                raise ValueError(f"Unknown customer: {customer_id}")

            customer.received_amount = received_amount.quantize(Decimal("0.01"))
            self._recalculate_customer_billing(customer)
            if customer.balance_amount <= Decimal("0.00"):
                for order in customer.orders:
                    if order.status not in {"CANCELED", "FULFILLED"}:
                        order.status = "FULFILLED"
                        order.updated_on = datetime.now(tz=timezone.utc)
            session.commit()

    def add_payment_for_order(
        self,
        *,
        store_id: str,
        customer_id: str,
        order_id: str,
        paid_amount: Decimal,
        payment_method: str,
        notes: str,
    ) -> None:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        normalized_order_id = order_id.strip()
        if not normalized_store_id or not normalized_customer_id or not normalized_order_id:
            raise ValueError("Store, customer, and order are required before recording payment.")

        with self._session_factory() as session:
            order = session.scalar(
                select(OrderModel)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .where(
                    CustomerModel.store_id == normalized_store_id,
                    OrderModel.customer_id == normalized_customer_id,
                    OrderModel.order_id == normalized_order_id,
                )
            )
            if order is None:
                raise ValueError("The selected order could not be found for this customer.")

            payment_amount = paid_amount.quantize(Decimal("0.01"))
            current_paid = Decimal(order.paid_amount).quantize(Decimal("0.01"))
            order_total = Decimal(order.order_total).quantize(Decimal("0.01"))
            normalized_notes = notes.strip()
            if payment_amount < Decimal("0.00"):
                raise ValueError("Payment amount cannot be negative.")
            if payment_amount == Decimal("0.00"):
                if not normalized_notes:
                    raise ValueError("Payment amount must be greater than zero unless notes are provided.")
                if order.status == "READY" and order.bill_status == "UNPAID":
                    order.status = "DWP"
                    order.notes = normalized_notes
            if payment_amount > Decimal("0.00") and current_paid + payment_amount > order_total:
                raise ValueError("Payment amount cannot be greater than the selected order balance.")
            if payment_amount == Decimal("0.00"):
                if current_paid > order_total:
                    raise ValueError("The selected order is already overpaid.")

            now = datetime.now(tz=timezone.utc)
            order.paid_amount = (current_paid + payment_amount).quantize(Decimal("0.01"))
            order.bill_status = self._bill_status_for_amounts(order_total, order.paid_amount)
            order.updated_on = now
            order.payments.append(
                PaymentModel(
                    order_id=normalized_order_id,
                    customer_id=normalized_customer_id,
                    paid_amount=payment_amount,
                    payment_method=payment_method.strip(),
                    notes=normalized_notes,
                    payment_date=now,
                )
            )
            customer = order.customer
            customer.received_amount = (
                Decimal(customer.received_amount) + payment_amount
            ).quantize(Decimal("0.01"))
            self._recalculate_customer_billing(customer)
            session.commit()

    def mark_order_delivered_for_store(
        self,
        *,
        store_id: str,
        customer_id: str,
        order_id: str,
    ) -> None:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        normalized_order_id = order_id.strip()
        if not normalized_store_id or not normalized_customer_id or not normalized_order_id:
            raise ValueError("Store, customer, and order are required before marking delivery.")

        with self._session_factory() as session:
            order = session.scalar(
                select(OrderModel)
                .join(CustomerModel, CustomerModel.customer_id == OrderModel.customer_id)
                .where(
                    CustomerModel.store_id == normalized_store_id,
                    OrderModel.customer_id == normalized_customer_id,
                    OrderModel.order_id == normalized_order_id,
                )
            )
            if order is None:
                raise ValueError("The selected order could not be found for this customer.")
            if order.bill_status != "PAID":
                raise ValueError("Only paid orders can be marked delivered.")
            order.status = "DELIVERED"
            order.updated_on = datetime.now(tz=timezone.utc)
            session.commit()

    def update_measurement_for_store(
        self,
        *,
        store_id: str,
        customer_id: str,
        measurement_id: int,
        measurements: str,
        weight: Decimal | None = None,
    ) -> None:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        if not normalized_store_id or not normalized_customer_id:
            raise ValueError("Store and customer are required before updating measurements.")
        if measurement_id <= 0:
            raise ValueError("Measurement selection is required.")

        with self._session_factory() as session:
            measurement = session.scalar(
                select(MeasurementModel)
                .join(CustomerModel, CustomerModel.customer_id == MeasurementModel.customer_id)
                .where(
                    CustomerModel.store_id == normalized_store_id,
                    MeasurementModel.customer_id == normalized_customer_id,
                    MeasurementModel.measurement_id == measurement_id,
                )
            )
            if measurement is None:
                raise ValueError("The selected measurement could not be found for this customer.")
            normalized_weight = self._normalize_weight(weight)
            measurement.measurements = measurements.strip()
            if normalized_weight is not None:
                measurement.weight = normalized_weight
            measurement.measurement_date = datetime.now(tz=timezone.utc)
            session.commit()

    def save_measurement_for_store(
        self,
        *,
        store_id: str,
        customer_id: str,
        item_id: str,
        item_name: str,
        measurements: str,
        measurement_id: int | None = None,
        weight: Decimal | None = None,
    ) -> None:
        normalized_store_id = store_id.strip()
        normalized_customer_id = customer_id.strip()
        normalized_item_id = item_id.strip()
        normalized_item_name = item_name.strip()
        normalized_measurements = measurements.strip()
        normalized_weight = self._normalize_weight(weight)
        if not normalized_store_id or not normalized_customer_id or not normalized_item_id:
            raise ValueError("Store, customer, and item are required before saving measurements.")
        if not normalized_measurements and normalized_weight is None:
            return

        with self._session_factory() as session:
            customer = session.scalar(
                select(CustomerModel).where(
                    CustomerModel.store_id == normalized_store_id,
                    CustomerModel.customer_id == normalized_customer_id,
                )
            )
            if customer is None:
                raise ValueError("The selected customer could not be found for this store.")
            item = session.scalar(
                select(ItemModel).where(
                    ItemModel.store_id == normalized_store_id,
                    ItemModel.item_id == normalized_item_id,
                )
            )
            if item is None:
                raise ValueError("The selected item could not be found for this store.")

            measurement = None
            if measurement_id is not None:
                measurement = session.scalar(
                    select(MeasurementModel).where(
                        MeasurementModel.customer_id == normalized_customer_id,
                        MeasurementModel.measurement_id == measurement_id,
                    )
                )
            if measurement is None:
                measurement = session.scalar(
                    select(MeasurementModel).where(
                        MeasurementModel.customer_id == normalized_customer_id,
                        MeasurementModel.item_id == normalized_item_id,
                    )
                )

            now = datetime.now(tz=timezone.utc)
            if measurement is None:
                measurement = MeasurementModel(
                    customer_id=normalized_customer_id,
                    item_id=normalized_item_id,
                    item_name=normalized_item_name or item.item_name,
                    measurements=normalized_measurements,
                    weight=normalized_weight,
                    measurement_date=now,
                )
                session.add(measurement)
            else:
                measurement.measurements = normalized_measurements
                if normalized_weight is not None:
                    measurement.weight = normalized_weight
                measurement.measurement_date = now
            session.flush()
            session.commit()

    def _backfill_measurements_for_customer(self, *, session: Session, customer_id: str) -> bool:
        customer_weight = self._measurement_weight_for_customer(session=session, customer_id=customer_id)
        order_items = session.scalars(
            select(OrderItemModel)
            .join(OrderModel, OrderModel.order_id == OrderItemModel.order_id)
            .where(
                OrderModel.customer_id == customer_id,
                OrderItemModel.measurement_id.is_(None),
                OrderItemModel.measurements != "",
            )
            .order_by(OrderItemModel.updated_on.asc(), OrderItemModel.order_item_id.asc())
        ).all()
        changed = False
        for order_item in order_items:
            measurement_text = order_item.measurements.strip()
            if not measurement_text:
                continue
            measurement = session.scalar(
                select(MeasurementModel).where(
                    MeasurementModel.customer_id == customer_id,
                    MeasurementModel.item_id == order_item.item_id,
                    MeasurementModel.measurements == measurement_text,
                )
            )
            if measurement is None:
                measurement = MeasurementModel(
                    customer_id=customer_id,
                    item_id=order_item.item_id,
                    item_name=order_item.item_name,
                    measurements=measurement_text,
                    weight=customer_weight,
                    measurement_date=self._ensure_utc(order_item.updated_on),
                )
                session.add(measurement)
                session.flush()
            order_item.measurement = measurement
            changed = True
        if changed:
            session.flush()
        return changed

    def _recalculate_customer_billing(self, customer: CustomerModel) -> None:
        total_billing = Decimal("0.00")
        for order in customer.orders:
            if order.status != "CANCELED":
                total_billing += Decimal(order.order_total)
        customer.total_billing = total_billing.quantize(Decimal("0.01"))
        balance = customer.total_billing - Decimal(customer.received_amount)
        customer.balance_amount = balance.quantize(Decimal("0.01"))

    def _build_order_from_input(
        self,
        *,
        customer_id: str,
        order_input: CustomerOrderCreateInput,
        created_on: datetime,
        session: Session | None = None,
    ) -> OrderModel:
        normalized_status = order_input.status.strip().upper()
        if normalized_status not in self.ORDER_STATUSES:
            raise ValueError(f"Unsupported order status: {order_input.status}")
        normalized_priority = order_input.priority.strip().title() or "Medium"
        if normalized_priority not in {"High", "Medium", "Low"}:
            raise ValueError("Priority must be High, Medium, or Low.")
        if order_input.paid_amount < Decimal("0.00"):
            raise ValueError("Paid amount cannot be negative.")
        if not order_input.items:
            raise ValueError("Add at least one order item before saving.")
        normalized_weight = self._normalize_weight(order_input.weight)

        order_total = Decimal("0.00")
        quantity = 0
        order_id = f"ORD-{created_on.strftime('%Y%m%d%H%M%S')}-{created_on.microsecond:06d}"
        order = OrderModel(
            order_id=order_id,
            customer_id=customer_id,
            title=order_input.title.strip() or "Customer order",
            quantity=0,
            order_total=Decimal("0.00"),
            paid_amount=order_input.paid_amount.quantize(Decimal("0.01")),
            status=normalized_status,
            bill_status=self._bill_status_for_amounts(Decimal("0.00"), order_input.paid_amount),
            notes="",
            due_on=self._ensure_optional_utc(order_input.due_on),
            priority=normalized_priority,
            created_by=order_input.created_by.strip(),
            created_on=created_on,
            updated_on=created_on,
        )
        for item_input in order_input.items:
            if item_input.quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")
            if item_input.rate < Decimal("0.00"):
                raise ValueError("Item rate cannot be negative.")
            line_amount = item_input.line_amount
            order_total += line_amount
            quantity += item_input.quantity
            measurement_text = item_input.measurements.strip()
            measurement = None
            if item_input.measurement_id is not None and session is not None:
                measurement = session.get(MeasurementModel, item_input.measurement_id)
                if measurement is None or measurement.customer_id != customer_id:
                    raise ValueError("The selected measurement could not be found for this customer.")
                if normalized_weight is not None:
                    measurement.weight = normalized_weight
                measurement_text = measurement.measurements
            elif measurement_text or normalized_weight is not None:
                measurement = MeasurementModel(
                    customer_id=customer_id,
                    item_id=item_input.item_id.strip(),
                    item_name=item_input.item_name.strip(),
                    measurements=measurement_text,
                    weight=normalized_weight,
                    measurement_date=self._ensure_utc(item_input.updated_on),
                )
            for _unit_index in range(item_input.quantity):
                order.items.append(
                    OrderItemModel(
                        order_id=order_id,
                        item_id=item_input.item_id.strip(),
                        item_name=item_input.item_name.strip(),
                        quantity=1,
                        measurement=measurement,
                        measurements=measurement_text,
                        rate=item_input.rate.quantize(Decimal("0.01")),
                        line_amount=item_input.rate.quantize(Decimal("0.01")),
                        status=(item_input.status.strip().upper() or normalized_status),
                        updated_on=self._ensure_utc(item_input.updated_on),
                        updated_by=item_input.updated_by.strip(),
                    )
                )

        order.quantity = quantity
        order.order_total = order_total.quantize(Decimal("0.01"))
        if order.paid_amount > order.order_total:
            raise ValueError("Paid amount cannot be greater than order total.")
        order.bill_status = self._bill_status_for_amounts(order.order_total, order.paid_amount)
        if order.paid_amount > Decimal("0.00"):
            order.payments.append(
                PaymentModel(
                    order_id=order_id,
                    customer_id=customer_id,
                    paid_amount=order.paid_amount,
                    payment_method="",
                    notes="",
                    payment_date=created_on,
                )
            )
        return order

    def _ensure_schema_columns(self) -> None:
        inspector = inspect(self._engine)
        table_names = set(inspector.get_table_names())
        statements_by_table = {
            "ops_payments": {
                "payment_method": "ALTER TABLE ops_payments ADD COLUMN payment_method VARCHAR(80) NOT NULL DEFAULT ''",
                "notes": "ALTER TABLE ops_payments ADD COLUMN notes VARCHAR(240) NOT NULL DEFAULT ''",
            },
            "ops_customers": {
                "store_id": "ALTER TABLE ops_customers ADD COLUMN store_id VARCHAR(50)",
                "is_whatsapp": "ALTER TABLE ops_customers ADD COLUMN is_whatsapp BOOLEAN NOT NULL DEFAULT 0",
            },
            "ops_orders": {
                "due_on": "ALTER TABLE ops_orders ADD COLUMN due_on DATETIME",
                "priority": "ALTER TABLE ops_orders ADD COLUMN priority VARCHAR(40) NOT NULL DEFAULT 'Medium'",
                "created_by": "ALTER TABLE ops_orders ADD COLUMN created_by VARCHAR(150) NOT NULL DEFAULT ''",
                "paid_amount": "ALTER TABLE ops_orders ADD COLUMN paid_amount NUMERIC(12, 2) NOT NULL DEFAULT 0",
                "bill_status": "ALTER TABLE ops_orders ADD COLUMN bill_status VARCHAR(40) NOT NULL DEFAULT 'UNPAID'",
            },
            "ops_order_items": {
                "measurement_id": "ALTER TABLE ops_order_items ADD COLUMN measurement_id INTEGER",
                "measurements": "ALTER TABLE ops_order_items ADD COLUMN measurements VARCHAR(240) NOT NULL DEFAULT ''",
                "assigned_worker_id": "ALTER TABLE ops_order_items ADD COLUMN assigned_worker_id VARCHAR(50) NOT NULL DEFAULT ''",
                "assigned_worker_name": "ALTER TABLE ops_order_items ADD COLUMN assigned_worker_name VARCHAR(150) NOT NULL DEFAULT ''",
                "assigned_on": "ALTER TABLE ops_order_items ADD COLUMN assigned_on DATETIME",
            },
            "ops_items": {
                "making_charges": "ALTER TABLE ops_items ADD COLUMN making_charges NUMERIC(12, 2) NOT NULL DEFAULT 0",
            },
            "ops_measurements": {
                "weight": "ALTER TABLE ops_measurements ADD COLUMN weight NUMERIC(8, 2)",
            },
        }

        missing_statements: list[str] = []
        for table_name, column_statements in statements_by_table.items():
            if table_name not in table_names:
                continue
            existing_columns = {
                column["name"]
                for column in inspector.get_columns(table_name)
            }
            missing_statements.extend(
                statement
                for column_name, statement in column_statements.items()
                if column_name not in existing_columns
            )

        if missing_statements:
            with self._engine.begin() as connection:
                for statement in missing_statements:
                    connection.exec_driver_sql(statement)
        self._sync_order_bill_statuses()
        self._sync_order_item_statuses()

    def _sync_order_bill_statuses(self) -> None:
        with self._session_factory() as session:
            rows = session.scalars(select(OrderModel)).all()
            changed = False
            for row in rows:
                bill_status = self._bill_status_for_amounts(
                    Decimal(row.order_total),
                    Decimal(row.paid_amount),
                )
                if row.bill_status != bill_status:
                    row.bill_status = bill_status
                    changed = True
            if changed:
                session.commit()

    def _sync_order_item_statuses(self) -> None:
        with self._session_factory() as session:
            rows = session.scalars(
                select(OrderItemModel).where(OrderItemModel.status == "INSTITCCHING")
            ).all()
            if not rows:
                return
            for row in rows:
                row.status = "INSTITCHING"
            session.commit()

    def _bill_status_for_amounts(self, order_total: Decimal, paid_amount: Decimal) -> str:
        normalized_total = Decimal(order_total).quantize(Decimal("0.01"))
        normalized_paid = Decimal(paid_amount).quantize(Decimal("0.01"))
        if normalized_total <= Decimal("0.00") or normalized_paid <= Decimal("0.00"):
            return "UNPAID"
        if normalized_paid >= normalized_total:
            return "PAID"
        return "PARTPAID"

    def _normalize_weight(self, weight: Decimal | None) -> Decimal | None:
        if weight is None:
            return None
        normalized_weight = Decimal(weight).quantize(Decimal("0.01"))
        if normalized_weight < Decimal("0.00"):
            raise ValueError("Customer weight cannot be negative.")
        return normalized_weight

    def _measurement_weight_for_customer(self, *, session: Session, customer_id: str) -> Decimal | None:
        row = session.scalar(
            select(MeasurementModel)
            .where(
                MeasurementModel.customer_id == customer_id,
                MeasurementModel.weight.is_not(None),
            )
            .order_by(MeasurementModel.measurement_date.desc(), MeasurementModel.measurement_id.desc())
        )
        if row is None or row.weight is None:
            return None
        return Decimal(row.weight).quantize(Decimal("0.01"))

    def _customer_search_filter(self, normalized_query: str):
        return (
            (func.lower(CustomerModel.full_name).contains(normalized_query))
            | (func.lower(CustomerModel.mobile).contains(normalized_query))
            | (func.lower(CustomerModel.email).contains(normalized_query))
        )

    def _seed_if_needed(self) -> None:
        with self._session_factory() as session:
            customer_count = session.scalar(select(func.count()).select_from(CustomerModel)) or 0
            if customer_count:
                return

            now = datetime.now(tz=timezone.utc)
            customer_1 = CustomerModel(
                customer_id="CUS-1001",
                full_name="Apex Retail",
                mobile="+15550100001",
                email="ops@apex-retail.local",
                address="19 Market Road, Seattle",
                created_on=now - timedelta(days=20),
                total_billing=Decimal("0.00"),
                received_amount=Decimal("600.00"),
                balance_amount=Decimal("0.00"),
            )
            customer_1.orders = [
                OrderModel(
                    order_id="ORD-1001",
                    customer_id="CUS-1001",
                    title="Seasonal inventory batch",
                    quantity=10,
                    order_total=Decimal("600.00"),
                    paid_amount=Decimal("600.00"),
                    bill_status="PAID",
                    status="FULFILLED",
                    notes="Paid in full and closed.",
                    created_on=now - timedelta(days=10),
                    updated_on=now - timedelta(days=2),
                )
            ]
            self._recalculate_customer_billing(customer_1)

            customer_2 = CustomerModel(
                customer_id="CUS-1002",
                full_name="Northwind Foods",
                mobile="+15550100002",
                email="orders@northwind.local",
                address="42 Distribution Park, Austin",
                created_on=now - timedelta(days=14),
                total_billing=Decimal("0.00"),
                received_amount=Decimal("300.00"),
                balance_amount=Decimal("0.00"),
            )
            customer_2.orders = [
                OrderModel(
                    order_id="ORD-1002",
                    customer_id="CUS-1002",
                    title="Cold storage shipment",
                    quantity=6,
                    order_total=Decimal("450.00"),
                    paid_amount=Decimal("0.00"),
                    bill_status="UNPAID",
                    status="READY",
                    notes="Waiting for dispatch window.",
                    created_on=now - timedelta(days=4),
                    updated_on=now - timedelta(hours=6),
                ),
                OrderModel(
                    order_id="ORD-1003",
                    customer_id="CUS-1002",
                    title="Return pallet recovery",
                    quantity=2,
                    order_total=Decimal("150.00"),
                    paid_amount=Decimal("0.00"),
                    bill_status="UNPAID",
                    status="INPROGRESS",
                    notes="Processing in warehouse.",
                    created_on=now - timedelta(days=2),
                    updated_on=now - timedelta(hours=3),
                ),
            ]
            self._recalculate_customer_billing(customer_2)

            session.add_all([customer_1, customer_2])
            session.commit()

    def _to_customer_row(self, row: CustomerModel) -> CustomerRow:
        return CustomerRow(
            customer_id=row.customer_id,
            store_id=row.store_id,
            full_name=row.full_name,
            mobile=row.mobile,
            email=row.email,
            address=row.address,
            is_whatsapp=bool(row.is_whatsapp),
            created_on=self._ensure_utc(row.created_on),
            total_billing=Decimal(row.total_billing).quantize(Decimal("0.01")),
            received_amount=Decimal(row.received_amount).quantize(Decimal("0.01")),
            balance_amount=Decimal(row.balance_amount).quantize(Decimal("0.01")),
        )

    def _to_order_row(self, row: OrderModel) -> OrderRow:
        return OrderRow(
            order_id=row.order_id,
            customer_id=row.customer_id,
            customer_name=row.customer.full_name,
            title=row.title,
            quantity=row.quantity,
            order_total=Decimal(row.order_total).quantize(Decimal("0.01")),
            paid_amount=Decimal(row.paid_amount).quantize(Decimal("0.01")),
            bill_status=row.bill_status,
            status=row.status,
            notes=row.notes,
            due_on=self._ensure_optional_utc(row.due_on),
            priority=row.priority,
            created_by=row.created_by,
            created_on=self._ensure_utc(row.created_on),
            updated_on=self._ensure_utc(row.updated_on),
        )

    def _to_order_item_row(self, row: OrderItemModel) -> OrderItemRow:
        return OrderItemRow(
            order_item_id=row.order_item_id,
            order_id=row.order_id,
            item_id=row.item_id,
            item_name=row.item_name,
            quantity=row.quantity,
            measurement_id=row.measurement_id,
            measurements=self._measurement_text_for_item(row),
            rate=Decimal(row.rate).quantize(Decimal("0.01")),
            line_amount=Decimal(row.line_amount).quantize(Decimal("0.01")),
            status=row.status,
            updated_on=self._ensure_utc(row.updated_on),
            updated_by=row.updated_by,
        )

    def _to_measurement_row(
        self,
        row: MeasurementModel,
        *,
        fallback_weight: Decimal | None = None,
    ) -> MeasurementRow:
        return MeasurementRow(
            measurement_id=row.measurement_id,
            customer_id=row.customer_id,
            item_id=row.item_id,
            item_name=row.item_name,
            measurements=row.measurements,
            measurement_date=self._ensure_utc(row.measurement_date),
            weight=(
                Decimal(row.weight).quantize(Decimal("0.01"))
                if row.weight is not None
                else fallback_weight
            ),
        )

    def _measurement_text_for_item(self, item: OrderItemModel) -> str:
        if item.measurement is not None and item.measurement.measurements:
            return item.measurement.measurements
        return item.measurements

    def _to_customer_summary_row(self, row: CustomerModel) -> CustomerSummaryRow:
        last_order_on = max(
            (self._ensure_utc(order.created_on) for order in row.orders),
            default=None,
        )
        return CustomerSummaryRow(
            customer_id=row.customer_id,
            full_name=row.full_name,
            mobile=row.mobile,
            email=row.email,
            last_order_on=last_order_on,
            balance_amount=Decimal(row.balance_amount).quantize(Decimal("0.01")),
        )

    def _to_item_row(self, row: ItemModel) -> ItemRow:
        return ItemRow(
            item_id=row.item_id,
            store_id=row.store_id,
            item_name=row.item_name,
            cost=Decimal(row.cost).quantize(Decimal("0.01")),
            making_charges=Decimal(row.making_charges).quantize(Decimal("0.01")),
            created_on=self._ensure_utc(row.created_on),
            updated_on=self._ensure_utc(row.updated_on),
        )

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _ensure_optional_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return self._ensure_utc(value)
