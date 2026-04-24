from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.operations.services import (
    CustomerOrderCreateInput,
    OperationsService,
    OrderItemCreateInput,
)
from app.platform.db.session import build_engine, build_session_factory


def test_manager_customer_dashboard_rows_are_store_scoped_and_calculated(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    created_on = datetime(2026, 4, 23, 10, 0, tzinfo=timezone.utc)
    due_on = datetime(2026, 4, 30, tzinfo=timezone.utc)
    service.create_customer_with_orders(
        store_id="store-1",
        full_name="Ajay Thombare",
        mobile="9730872698",
        email="",
        address="Pune",
        is_whatsapp=True,
        orders=[
            CustomerOrderCreateInput(
                title="Pant + Shirt",
                created_by="Manager User",
                due_on=due_on,
                priority="Medium",
                status="NEW",
                paid_amount=Decimal("0.00"),
                items=(
                    OrderItemCreateInput(
                        item_id="item-pant",
                        item_name="Pant",
                        quantity=1,
                        measurements="",
                        rate=Decimal("1000.00"),
                        status="NEW",
                        updated_on=created_on,
                        updated_by="Manager User",
                    ),
                    OrderItemCreateInput(
                        item_id="item-shirt",
                        item_name="Shirt",
                        quantity=1,
                        measurements="",
                        rate=Decimal("500.00"),
                        status="NEW",
                        updated_on=created_on,
                        updated_by="Manager User",
                    ),
                ),
            )
        ],
    )

    summaries = service.list_customer_summaries_for_store(store_id="store-1")
    paged_summaries = service.list_customer_summaries_for_store(
        store_id="store-1",
        limit=1,
        offset=0,
    )
    queue = service.list_order_queue_for_store(store_id="store-1")

    assert service.count_customer_summaries_for_store(store_id="store-1") == 1
    assert len(summaries) == 1
    assert paged_summaries == summaries
    assert summaries[0].full_name == "Ajay Thombare"
    assert summaries[0].mobile == "9730872698"
    assert summaries[0].balance_amount == Decimal("1500.00")
    assert summaries[0].last_order_on is not None
    assert [row.item_name for row in queue] == ["Pant", "Shirt"]
    assert {row.customer_name for row in queue} == {"Ajay Thombare"}
    assert {row.due_date for row in queue} == {due_on}


def test_manager_customer_search_is_limited_to_active_store(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    for store_id, name, mobile in (
        ("store-1", "Ajay Thombare", "9730872698"),
        ("store-2", "Ajay Other", "1111111111"),
    ):
        service.create_customer_with_orders(
            store_id=store_id,
            full_name=name,
            mobile=mobile,
            email="",
            address="Pune",
            is_whatsapp=False,
            orders=[
                CustomerOrderCreateInput(
                    title="Pant",
                    created_by="Manager User",
                    due_on=None,
                    priority="Low",
                    status="NEW",
                    paid_amount=Decimal("0.00"),
                    items=(
                        OrderItemCreateInput(
                            item_id="item-pant",
                            item_name="Pant",
                            quantity=1,
                            measurements="",
                            rate=Decimal("1000.00"),
                            status="NEW",
                            updated_on=datetime.now(tz=timezone.utc),
                            updated_by="Manager User",
                        ),
                    ),
                )
            ],
        )

    rows = service.search_customer_summaries_for_store(store_id="store-1", query="ajay")

    assert service.count_search_customer_summaries_for_store(store_id="store-1", query="ajay") == 1
    assert [row.mobile for row in rows] == ["9730872698"]
