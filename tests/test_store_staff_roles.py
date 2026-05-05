from __future__ import annotations

from datetime import datetime, timezone

from app.admin.services import AdminUserManagementService
from app.platform.db.session import build_engine, build_session_factory


def _build_service(tmp_path) -> AdminUserManagementService:
    db_path = tmp_path / "staff-roles.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    return AdminUserManagementService(
        engine=engine,
        session_factory=build_session_factory(engine),
        password_hasher=lambda password: f"hashed:{password}",
    )


def _create_store_admin(service: AdminUserManagementService) -> str:
    result = service.create_store_with_admin(
        store_code="ROL",
        store_name="Role Store",
        address="Pune",
        city="Pune",
        manager_name="Store Lead",
        contact_info="9999999999 | role@example.com",
        owner_name="Owner",
        owner_mobile="9999999999",
        owner_email="owner@example.com",
        status="Active",
        store_admin_username="role-admin",
        store_admin_full_name="Role Admin",
        store_admin_mobile="9999999999",
        store_admin_email="admin@example.com",
    )
    assert result.store_admin_user_id is not None
    return result.store_admin_user_id


def test_accountant_role_is_seeded_with_worker_payment_permissions(tmp_path) -> None:
    service = _build_service(tmp_path)

    accountant = service.get_role_definition("Accountant")

    assert accountant is not None
    assert "worker:payment:view" in accountant.permissions
    assert "worker:payment:update" in accountant.permissions
    assert "Accountant" in service.available_roles_for_actor(_create_store_admin(service))


def test_store_admin_can_assign_multiple_staff_roles_and_union_permissions(tmp_path) -> None:
    service = _build_service(tmp_path)
    store_admin_user_id = _create_store_admin(service)

    staff = service.create_staff_member(
        actor_user_id=store_admin_user_id,
        username="manager-accountant",
        full_name="Manager Accountant",
        contact_number="8888888888",
        speciality="Orders and payments",
        joining_date=datetime(2026, 4, 26, tzinfo=timezone.utc),
        role_names=["Manager", "Accountant"],
    )
    profile = service.get_user_profile(staff.user_id)
    staff_profile = service.get_staff_member_profile(
        actor_user_id=store_admin_user_id,
        user_id=staff.user_id,
    )

    assert profile is not None
    assert profile.roles == ("Manager", "Accountant")
    assert "customer:create" in profile.permissions
    assert "worker:payment:update" in profile.permissions
    assert staff_profile is not None
    assert staff_profile.roles == ("Manager", "Accountant")

    service.update_staff_member(
        actor_user_id=store_admin_user_id,
        user_id=staff.user_id,
        full_name="Manager Accountant",
        contact_number="8888888888",
        speciality="Payments only",
        joining_date=datetime(2026, 4, 26, tzinfo=timezone.utc),
        role_names=["Accountant"],
    )
    updated_profile = service.get_user_profile(staff.user_id)

    assert updated_profile is not None
    assert updated_profile.roles == ("Accountant",)
    assert "worker:payment:update" in updated_profile.permissions
    assert "customer:create" not in updated_profile.permissions
