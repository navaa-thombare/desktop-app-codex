from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.operations.services import (
    CustomerOrderCreateInput,
    OrderItemModel,
    OrderModel,
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
                paid_amount=Decimal("500.00"),
                weight=Decimal("72.50"),
                items=(
                    OrderItemCreateInput(
                        item_id="item-pant",
                        item_name="Pant",
                        quantity=1,
                        measurements="waist 34",
                        rate=Decimal("1000.00"),
                        status="HOLD",
                        updated_on=created_on,
                        updated_by="Manager User",
                    ),
                    OrderItemCreateInput(
                        item_id="item-shirt",
                        item_name="Shirt",
                        quantity=1,
                        measurements="chest 40",
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
    history = service.list_customer_order_history_for_store(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
    )
    payments = service.list_payment_history_for_store(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
    )
    measurements = service.list_measurements_for_customer(
        customer_id=summaries[0].customer_id,
    )

    assert service.count_customer_summaries_for_store(store_id="store-1") == 1
    assert len(summaries) == 1
    assert paged_summaries == summaries
    assert summaries[0].full_name == "Ajay Thombare"
    assert summaries[0].mobile == "9730872698"
    assert summaries[0].balance_amount == Decimal("1000.00")
    assert summaries[0].last_order_on is not None
    assert [row.item_name for row in queue] == ["Pant", "Shirt"]
    assert {row.customer_name for row in queue} == {"Ajay Thombare"}
    assert {row.due_date for row in queue} == {due_on}
    assert [row.item_name for row in history] == ["Pant", "Shirt"]
    assert {row.order_quantity for row in history} == {2}
    assert [row.measurements for row in history] == ["waist 34", "chest 40"]
    assert [row.line_amount for row in history] == [Decimal("1000.00"), Decimal("500.00")]
    assert {row.created_by for row in history} == {"Manager User"}
    assert {row.paid_amount for row in history} == {Decimal("500.00")}
    assert {row.bill_status for row in history} == {"PARTPAID"}
    assert [(row.order_id, row.paid_amount) for row in payments] == [
        (history[0].order_id, Decimal("500.00"))
    ]
    assert {row.item_name: row.measurements for row in measurements} == {
        "Pant": "waist 34",
        "Shirt": "chest 40",
    }
    assert {row.weight for row in measurements} == {Decimal("72.50")}
    assert {row.measurement_date for row in measurements} == {created_on}

    service.add_payment_for_order(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
        order_id=history[0].order_id,
        paid_amount=Decimal("250.00"),
        payment_method="Cash",
        notes="Second payment",
    )
    updated_summary = service.list_customer_summaries_for_store(store_id="store-1")[0]
    updated_history = service.list_customer_order_history_for_store(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
    )
    updated_payments = service.list_payment_history_for_store(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
    )

    assert updated_summary.balance_amount == Decimal("750.00")
    assert {row.paid_amount for row in updated_history} == {Decimal("750.00")}
    assert {row.bill_status for row in updated_history} == {"PARTPAID"}
    assert [row.paid_amount for row in updated_payments] == [Decimal("250.00"), Decimal("500.00")]
    assert updated_payments[0].payment_method == "Cash"
    assert updated_payments[0].notes == "Second payment"

    shirt_measurement_id = next(
        row.measurement_id for row in measurements if row.item_name == "Shirt"
    )
    service.update_measurement_for_store(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
        measurement_id=shirt_measurement_id,
        measurements="chest 42",
    )
    updated_measurements = service.list_measurements_for_customer(
        customer_id=summaries[0].customer_id,
    )
    updated_measurement_lookup = {
        row.item_name: row.measurements for row in updated_measurements
    }
    assert updated_measurement_lookup["Shirt"] == "chest 42"

    service.add_payment_for_order(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
        order_id=history[0].order_id,
        paid_amount=Decimal("750.00"),
        payment_method="Cash",
        notes="Final payment",
    )
    paid_history = service.list_customer_order_history_for_store(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
    )
    assert {row.bill_status for row in paid_history} == {"PAID"}
    service.mark_order_delivered_for_store(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
        order_id=history[0].order_id,
    )
    delivered_history = service.list_customer_order_history_for_store(
        store_id="store-1",
        customer_id=summaries[0].customer_id,
    )
    assert {row.order_status for row in delivered_history} == {"DELIVERED"}


def test_ordered_item_and_assignment_rows_expand_by_item_quantity(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    due_on = datetime(2026, 5, 2, tzinfo=timezone.utc)
    service.create_customer_with_orders(
        store_id="store-1",
        full_name="Customer A",
        mobile="9000000100",
        email="",
        address="Pune",
        is_whatsapp=False,
        orders=[
            CustomerOrderCreateInput(
                title="Shirt + Pant",
                created_by="Manager User",
                due_on=due_on,
                priority="High",
                status="NEW",
                paid_amount=Decimal("0.00"),
                weight=Decimal("68.25"),
                items=(
                    OrderItemCreateInput(
                        item_id="item-shirt",
                        item_name="Shirt",
                        quantity=3,
                        measurements="chest 40",
                        rate=Decimal("500.00"),
                        status="NEW",
                        updated_on=datetime.now(tz=timezone.utc),
                        updated_by="Manager User",
                    ),
                    OrderItemCreateInput(
                        item_id="item-pant",
                        item_name="Pant",
                        quantity=2,
                        measurements="waist 34",
                        rate=Decimal("700.00"),
                        status="HOLD",
                        updated_on=datetime.now(tz=timezone.utc),
                        updated_by="Manager User",
                    ),
                ),
            )
        ],
    )

    ordered_rows = service.list_order_queue_for_store(store_id="store-1")
    assignment_rows = service.list_order_management_items_for_store(store_id="store-1")
    summary = service.order_management_summary_for_store(store_id="store-1", worker_count=1)

    assert [row.item_name for row in ordered_rows].count("Shirt") == 3
    assert [row.item_name for row in ordered_rows].count("Pant") == 2
    assert len(ordered_rows) == 5
    assert [row.item_name for row in assignment_rows].count("Shirt") == 3
    assert [row.item_name for row in assignment_rows].count("Pant") == 2
    assert len(assignment_rows) == 5
    assert summary.new_hold_items == 5
    assert summary.total_items == 5

    history = service.list_customer_order_history_for_store(
        store_id="store-1",
        customer_id=service.list_customer_summaries_for_store(store_id="store-1")[0].customer_id,
    )
    assert {row.order_quantity for row in history} == {5}
    assert [row.item_name for row in history].count("Shirt") == 3
    assert [row.item_name for row in history].count("Pant") == 2
    assert {row.quantity for row in history} == {1}


def test_store_items_include_making_charges(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    item_id = service.create_item(
        store_id="store-1",
        item_name="Shirt",
        cost=Decimal("500.00"),
        making_charges=Decimal("125.50"),
    )
    item = service.get_item(store_id="store-1", item_id=item_id)

    assert item is not None
    assert item.making_charges == Decimal("125.50")

    service.update_item(
        store_id="store-1",
        item_id=item_id,
        item_name="Shirt",
        cost=Decimal("550.00"),
        making_charges=Decimal("150.00"),
    )
    updated_item = service.get_item(store_id="store-1", item_id=item_id)

    assert updated_item is not None
    assert updated_item.cost == Decimal("550.00")
    assert updated_item.making_charges == Decimal("150.00")


def test_worker_payment_items_filter_status_worker_and_sum_making_charges(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    shirt_id = service.create_item(
        store_id="store-1",
        item_name="Shirt",
        cost=Decimal("500.00"),
        making_charges=Decimal("125.00"),
    )
    pant_id = service.create_item(
        store_id="store-1",
        item_name="Pant",
        cost=Decimal("700.00"),
        making_charges=Decimal("200.00"),
    )
    service.create_customer_with_orders(
        store_id="store-1",
        full_name="Payment Customer",
        mobile="9000000111",
        email="",
        address="Pune",
        is_whatsapp=False,
        orders=[
            CustomerOrderCreateInput(
                title="Shirt + Pant",
                created_by="Manager User",
                due_on=datetime(2026, 5, 2, tzinfo=timezone.utc),
                priority="High",
                status="NEW",
                paid_amount=Decimal("0.00"),
                items=(
                    OrderItemCreateInput(
                        item_id=shirt_id,
                        item_name="Shirt",
                        quantity=2,
                        measurements="chest 40",
                        rate=Decimal("500.00"),
                        status="NEW",
                        updated_on=datetime.now(tz=timezone.utc),
                        updated_by="Manager User",
                    ),
                    OrderItemCreateInput(
                        item_id=pant_id,
                        item_name="Pant",
                        quantity=1,
                        measurements="waist 34",
                        rate=Decimal("700.00"),
                        status="HOLD",
                        updated_on=datetime.now(tz=timezone.utc),
                        updated_by="Manager User",
                    ),
                ),
            )
        ],
    )
    rows = service.list_order_management_items_for_store(store_id="store-1")
    shirt_rows = [row for row in rows if row.item_name == "Shirt"]
    pant_row = next(row for row in rows if row.item_name == "Pant")
    for shirt_row in shirt_rows:
        service.assign_order_item_to_worker(
            store_id="store-1",
            order_item_id=shirt_row.order_item_id,
            worker_id="worker-1",
            worker_name="Worker One",
        )
        service.update_order_item_status_for_store(
            store_id="store-1",
            order_item_id=shirt_row.order_item_id,
            status="READY",
        )
    service.assign_order_item_to_worker(
        store_id="store-1",
        order_item_id=pant_row.order_item_id,
        worker_id="worker-2",
        worker_name="Worker Two",
    )

    all_payment_rows = service.list_worker_payment_items_for_store(store_id="store-1")
    worker_one_rows = service.list_worker_payment_items_for_store(
        store_id="store-1",
        worker_id="worker-1",
    )

    assert len(all_payment_rows) == 2
    assert [row.item_name for row in worker_one_rows] == ["Shirt", "Shirt"]
    assert {row.item_status for row in all_payment_rows} == {"READY"}
    assert sum((row.making_charges for row in all_payment_rows), Decimal("0.00")) == Decimal("250.00")


def test_ready_unpaid_order_can_be_marked_dwp_with_notes(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    customer_id = service.create_customer_with_orders(
        store_id="store-1",
        full_name="Ready Customer",
        mobile="9000000001",
        email="",
        address="Pune",
        is_whatsapp=False,
        orders=[
            CustomerOrderCreateInput(
                title="Pant",
                created_by="Manager User",
                due_on=None,
                priority="Medium",
                status="READY",
                paid_amount=Decimal("0.00"),
                items=(
                    OrderItemCreateInput(
                        item_id="item-pant",
                        item_name="Pant",
                        quantity=1,
                        measurements="",
                        rate=Decimal("1000.00"),
                        status="HOLD",
                        updated_on=datetime.now(tz=timezone.utc),
                        updated_by="Manager User",
                    ),
                ),
            )
        ],
    )
    history = service.list_customer_order_history_for_store(
        store_id="store-1",
        customer_id=customer_id,
    )

    assert history[0].bill_status == "UNPAID"
    assert history[0].order_status == "READY"

    service.add_payment_for_order(
        store_id="store-1",
        customer_id=customer_id,
        order_id=history[0].order_id,
        paid_amount=Decimal("0.00"),
        payment_method="Cash",
        notes="Deliver without payment",
    )
    updated_history = service.list_customer_order_history_for_store(
        store_id="store-1",
        customer_id=customer_id,
    )
    payments = service.list_payment_history_for_store(
        store_id="store-1",
        customer_id=customer_id,
    )

    assert updated_history[0].bill_status == "UNPAID"
    assert updated_history[0].order_status == "DWP"
    assert len(payments) == 1
    assert payments[0].paid_amount == Decimal("0.00")
    assert payments[0].notes == "Deliver without payment"


def test_order_management_rows_summary_and_assignment(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    due_on = datetime(2026, 5, 1, tzinfo=timezone.utc)
    customer_id = service.create_customer_with_orders(
        store_id="store-1",
        full_name="Assignment Customer",
        mobile="9000000002",
        email="",
        address="Pune",
        is_whatsapp=False,
        orders=[
            CustomerOrderCreateInput(
                title="Pant",
                created_by="Manager User",
                due_on=due_on,
                priority="High",
                status="NEW",
                paid_amount=Decimal("0.00"),
                items=(
                    OrderItemCreateInput(
                        item_id="item-pant",
                        item_name="Pant",
                        quantity=1,
                        measurements="",
                        rate=Decimal("1000.00"),
                        status="HOLD",
                        updated_on=datetime.now(tz=timezone.utc),
                        updated_by="Manager User",
                    ),
                ),
            )
        ],
    )

    rows = service.list_order_management_items_for_store(store_id="store-1")
    filtered_rows = service.list_order_management_items_for_store(
        store_id="store-1",
        due_date=due_on,
    )
    summary = service.order_management_summary_for_store(store_id="store-1", worker_count=3)

    assert customer_id
    assert len(rows) == 1
    assert len(filtered_rows) == 1
    assert rows[0].customer_name == "Assignment Customer"
    assert rows[0].item_name == "Pant"
    assert rows[0].priority == "High"
    assert rows[0].item_status == "HOLD"
    assert rows[0].status == "NEW"
    assert summary.new_hold_items == 1
    assert summary.worker_count == 3
    assert summary.todays_assigned == 0
    assert summary.total_items == 1

    service.assign_order_item_to_worker(
        store_id="store-1",
        order_item_id=rows[0].order_item_id,
        worker_id="worker-1",
        worker_name="Worker One",
    )
    assigned_rows = service.list_order_management_items_for_store(store_id="store-1")
    assigned_summary = service.order_management_summary_for_store(store_id="store-1", worker_count=3)

    assert assigned_rows[0].assigned_worker_id == "worker-1"
    assert assigned_rows[0].assigned_worker_name == "Worker One"
    assert assigned_rows[0].item_status == "ASSIGNED"
    assert assigned_summary.todays_assigned == 1

    service.assign_order_item_to_worker(
        store_id="store-1",
        order_item_id=rows[0].order_item_id,
        worker_id="worker-2",
        worker_name="Worker Two",
    )
    reassigned_rows = service.list_order_management_items_for_store(store_id="store-1")
    worker_assignments = service.list_worker_assignment_summary_for_store(store_id="store-1")
    work_rows = service.list_work_management_items_for_store(store_id="store-1")
    filtered_work_rows = service.list_work_management_items_for_store(
        store_id="store-1",
        worker_id="worker-2",
    )
    missing_worker_rows = service.list_work_management_items_for_store(
        store_id="store-1",
        worker_id="worker-1",
    )

    assert reassigned_rows[0].assigned_worker_id == "worker-2"
    assert reassigned_rows[0].assigned_worker_name == "Worker Two"
    assert reassigned_rows[0].item_status == "ASSIGNED"
    assert [row.assigned_worker_id for row in work_rows] == ["worker-2"]
    assert [row.assigned_worker_id for row in filtered_work_rows] == ["worker-2"]
    assert missing_worker_rows == ()
    assert worker_assignments[0].worker_id == "worker-2"
    assert worker_assignments[0].worker_name == "Worker Two"
    assert worker_assignments[0].total_assigned_items == 1
    assert worker_assignments[0].inprogress_items == 0

    with service._session_factory() as session:  # type: ignore[attr-defined]
        item = session.get(OrderItemModel, rows[0].order_item_id)
        item.status = "INSTITCHING"
        session.commit()

    assert service.list_order_management_items_for_store(store_id="store-1") == ()
    inprogress_assignments = service.list_worker_assignment_summary_for_store(store_id="store-1")
    assert inprogress_assignments[0].total_assigned_items == 0
    assert inprogress_assignments[0].inprogress_items == 1

    service.update_order_item_status_for_store(
        store_id="store-1",
        order_item_id=rows[0].order_item_id,
        status="HOLD",
    )
    hold_assignment_rows = service.list_order_management_items_for_store(store_id="store-1")
    hold_work_rows = service.list_work_management_items_for_store(store_id="store-1")
    hold_summary = service.order_management_summary_for_store(store_id="store-1", worker_count=3)
    assert hold_assignment_rows[0].item_status == "HOLD"
    assert hold_work_rows[0].item_status == "HOLD"
    assert hold_summary.new_hold_items == 1

    service.update_order_item_status_for_store(
        store_id="store-1",
        order_item_id=rows[0].order_item_id,
        status="READY",
    )
    ready_assignment_rows = service.list_order_management_items_for_store(store_id="store-1")
    ready_work_rows = service.list_work_management_items_for_store(store_id="store-1")
    ready_summary = service.order_management_summary_for_store(store_id="store-1", worker_count=3)
    assert ready_assignment_rows == ()
    assert ready_work_rows[0].item_status == "READY"
    assert ready_summary.total_items == 0


def test_operation_service_normalizes_legacy_institching_typo(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )
    customer_id = service.create_customer_with_orders(
        store_id="store-1",
        full_name="Legacy Status Customer",
        mobile="9000000003",
        email="",
        address="Pune",
        is_whatsapp=False,
        orders=[
            CustomerOrderCreateInput(
                title="Pant",
                created_by="Manager User",
                due_on=None,
                priority="High",
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
    row = service.list_order_management_items_for_store(store_id="store-1")[0]
    service.assign_order_item_to_worker(
        store_id="store-1",
        order_item_id=row.order_item_id,
        worker_id="worker-1",
        worker_name="Worker One",
    )
    with service._session_factory() as session:  # type: ignore[attr-defined]
        item = session.get(OrderItemModel, row.order_item_id)
        item.status = "INSTITCCHING"
        session.commit()

    OperationsService(engine=engine, session_factory=build_session_factory(engine))
    work_rows = service.list_work_management_items_for_store(
        store_id="store-1",
        worker_id="worker-1",
    )

    assert customer_id
    assert work_rows[0].item_status == "INSTITCHING"


def test_item_status_update_recalculates_only_parent_order_status(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    created_on = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
    customer_id = service.create_customer_with_orders(
        store_id="store-1",
        full_name="Multi Order Customer",
        mobile="9000000004",
        email="",
        address="Pune",
        is_whatsapp=False,
        orders=[
            CustomerOrderCreateInput(
                title="Two Shirts",
                created_by="Manager User",
                due_on=None,
                priority="Medium",
                status="NEW",
                paid_amount=Decimal("0.00"),
                weight=Decimal("68.25"),
                items=(
                    OrderItemCreateInput(
                        item_id="item-shirt",
                        item_name="Shirt",
                        quantity=1,
                        measurements="chest 40",
                        rate=Decimal("500.00"),
                        status="ASSIGNED",
                        updated_on=created_on,
                        updated_by="Manager User",
                    ),
                    OrderItemCreateInput(
                        item_id="item-shirt-2",
                        item_name="Shirt",
                        quantity=1,
                        measurements="chest 42",
                        rate=Decimal("500.00"),
                        status="ASSIGNED",
                        updated_on=created_on,
                        updated_by="Manager User",
                    ),
                ),
            ),
            CustomerOrderCreateInput(
                title="Pant",
                created_by="Manager User",
                due_on=None,
                priority="Medium",
                status="NEW",
                paid_amount=Decimal("0.00"),
                items=(
                    OrderItemCreateInput(
                        item_id="item-pant",
                        item_name="Pant",
                        quantity=1,
                        measurements="waist 34",
                        rate=Decimal("1000.00"),
                        status="ASSIGNED",
                        updated_on=created_on,
                        updated_by="Manager User",
                    ),
                ),
            ),
        ],
    )
    with service._session_factory() as session:  # type: ignore[attr-defined]
        orders = session.scalars(
            select(OrderModel)
            .where(OrderModel.customer_id == customer_id)
            .order_by(OrderModel.created_on.asc())
        ).all()
        target_order_id = orders[0].order_id
        other_order_id = orders[1].order_id
        target_item_ids = [item.order_item_id for item in orders[0].items]

    service.update_order_item_status_for_store(
        store_id="store-1",
        order_item_id=target_item_ids[0],
        status="INSTITCHING",
    )

    assert service.get_order(target_order_id).status == "INPROGRESS"
    assert service.get_order(other_order_id).status == "NEW"

    service.update_order_item_status_for_store(
        store_id="store-1",
        order_item_id=target_item_ids[0],
        status="READY",
    )

    assert service.get_order(target_order_id).status == "INPROGRESS"
    assert service.get_order(other_order_id).status == "NEW"

    service.update_order_item_status_for_store(
        store_id="store-1",
        order_item_id=target_item_ids[1],
        status="READY",
    )

    assert service.get_order(target_order_id).status == "READY"
    assert service.get_order(other_order_id).status == "NEW"


def test_customer_measurements_include_store_items_and_link_new_orders(tmp_path) -> None:
    db_path = tmp_path / "ops.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    service = OperationsService(
        engine=engine,
        session_factory=build_session_factory(engine),
    )

    shirt_id = service.create_item(
        store_id="store-1",
        item_name="Shirt",
        cost=Decimal("500.00"),
    )
    pant_id = service.create_item(
        store_id="store-1",
        item_name="Pant",
        cost=Decimal("1000.00"),
    )
    created_on = datetime(2026, 4, 23, 10, 0, tzinfo=timezone.utc)
    customer_id = service.create_customer_with_orders(
        store_id="store-1",
        full_name="Abcd Customer",
        mobile="9000000000",
        email="",
        address="Pune",
        is_whatsapp=False,
        orders=[
            CustomerOrderCreateInput(
                title="Shirt",
                created_by="Manager User",
                due_on=None,
                priority="Medium",
                status="NEW",
                paid_amount=Decimal("0.00"),
                weight=Decimal("68.25"),
                items=(
                    OrderItemCreateInput(
                        item_id=shirt_id,
                        item_name="Shirt",
                        quantity=1,
                        measurements="chest 40",
                        rate=Decimal("500.00"),
                        status="NEW",
                        updated_on=created_on,
                        updated_by="Manager User",
                    ),
                ),
            )
        ],
    )

    measurements = service.list_measurements_for_customer(
        customer_id=customer_id,
        store_id="store-1",
    )
    measurement_lookup = {row.item_name: row for row in measurements}

    assert measurement_lookup["Shirt"].measurements == "chest 40"
    assert measurement_lookup["Shirt"].weight == Decimal("68.25")
    assert measurement_lookup["Shirt"].measurement_id is not None
    assert measurement_lookup["Pant"].measurement_id is None
    assert measurement_lookup["Pant"].measurements == ""
    assert measurement_lookup["Pant"].weight == Decimal("68.25")

    service.save_measurement_for_store(
        store_id="store-1",
        customer_id=customer_id,
        item_id=pant_id,
        item_name="Pant",
        measurements="waist 34",
        weight=measurement_lookup["Pant"].weight,
    )
    updated_measurements = service.list_measurements_for_customer(
        customer_id=customer_id,
        store_id="store-1",
    )
    pant_measurement = next(row for row in updated_measurements if row.item_name == "Pant")
    assert pant_measurement.measurement_id is not None
    assert pant_measurement.weight == Decimal("68.25")

    service.create_order_for_customer(
        store_id="store-1",
        customer_id=customer_id,
        order=CustomerOrderCreateInput(
            title="Pant",
            created_by="Manager User",
            due_on=None,
            priority="Medium",
            status="NEW",
            paid_amount=Decimal("0.00"),
            items=(
                OrderItemCreateInput(
                    item_id=pant_id,
                    item_name="Pant",
                    quantity=1,
                    measurements="",
                    rate=Decimal("1000.00"),
                    status="NEW",
                    updated_on=datetime.now(tz=timezone.utc),
                    updated_by="Manager User",
                    measurement_id=pant_measurement.measurement_id,
                ),
            ),
        ),
    )
    history = service.list_customer_order_history_for_store(
        store_id="store-1",
        customer_id=customer_id,
    )

    assert any(row.item_name == "Pant" and row.measurements == "waist 34" for row in history)


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
