from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class CustomerModel(Base):
    __tablename__ = "ops_customers"

    customer_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    mobile: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(240), nullable=False)
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
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    customer: Mapped[CustomerModel] = relationship(back_populates="orders")


class ItemModel(Base):
    __tablename__ = "ops_items"

    item_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(160), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class CustomerRow:
    customer_id: str
    full_name: str
    mobile: str
    email: str
    address: str
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
    status: str
    notes: str
    created_on: datetime
    updated_on: datetime


@dataclass(frozen=True)
class ItemRow:
    item_id: str
    store_id: str
    item_name: str
    cost: Decimal
    created_on: datetime
    updated_on: datetime


class OperationsService:
    ORDER_STATUSES = (
        "NEW",
        "WAITING",
        "INPROGRESS",
        "HOLD",
        "READY",
        "DELIVERED",
        "CANCELED",
        "FULFILLED",
    )

    def __init__(self, *, engine, session_factory: sessionmaker[Session]) -> None:
        self._engine = engine
        self._session_factory = session_factory
        Base.metadata.create_all(bind=self._engine)
        self._seed_if_needed()

    def list_customers(self) -> tuple[CustomerRow, ...]:
        with self._session_factory() as session:
            rows = session.scalars(select(CustomerModel).order_by(CustomerModel.full_name.asc())).all()
            return tuple(self._to_customer_row(row) for row in rows)

    def list_orders(self) -> tuple[OrderRow, ...]:
        with self._session_factory() as session:
            rows = session.scalars(select(OrderModel).order_by(OrderModel.updated_on.desc())).all()
            return tuple(self._to_order_row(row) for row in rows)

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
    ) -> str:
        normalized_store_id = store_id.strip()
        normalized_item_name = item_name.strip()
        if not normalized_store_id:
            raise ValueError("Store context is required before creating an item.")
        if not normalized_item_name:
            raise ValueError("Item name is required.")
        if cost < Decimal("0.00"):
            raise ValueError("Item cost cannot be negative.")

        now = datetime.now(tz=timezone.utc)
        item_id = f"ITEM-{now.strftime('%Y%m%d%H%M%S')}-{now.microsecond:06d}"
        normalized_cost = cost.quantize(Decimal("0.01"))
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
            item.updated_on = datetime.now(tz=timezone.utc)
            session.commit()

    def get_customer(self, customer_id: str) -> CustomerRow | None:
        with self._session_factory() as session:
            row = session.get(CustomerModel, customer_id)
            if row is None:
                return None
            return self._to_customer_row(row)

    def get_order(self, order_id: str) -> OrderRow | None:
        with self._session_factory() as session:
            row = session.get(OrderModel, order_id)
            if row is None:
                return None
            return self._to_order_row(row)

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

    def _recalculate_customer_billing(self, customer: CustomerModel) -> None:
        total_billing = Decimal("0.00")
        for order in customer.orders:
            if order.status != "CANCELED":
                total_billing += Decimal(order.order_total)
        customer.total_billing = total_billing.quantize(Decimal("0.01"))
        balance = customer.total_billing - Decimal(customer.received_amount)
        customer.balance_amount = balance.quantize(Decimal("0.01"))

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
            full_name=row.full_name,
            mobile=row.mobile,
            email=row.email,
            address=row.address,
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
            status=row.status,
            notes=row.notes,
            created_on=self._ensure_utc(row.created_on),
            updated_on=self._ensure_utc(row.updated_on),
        )

    def _to_item_row(self, row: ItemModel) -> ItemRow:
        return ItemRow(
            item_id=row.item_id,
            store_id=row.store_id,
            item_name=row.item_name,
            cost=Decimal(row.cost).quantize(Decimal("0.01")),
            created_on=self._ensure_utc(row.created_on),
            updated_on=self._ensure_utc(row.updated_on),
        )

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
