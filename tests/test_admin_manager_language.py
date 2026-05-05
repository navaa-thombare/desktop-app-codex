from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.admin.services import AdminUserManagementService
from app.platform.db.session import build_engine, build_session_factory


def _build_service(tmp_path) -> AdminUserManagementService:
    db_path = tmp_path / "admin-language.db"
    engine = build_engine(f"sqlite+pysqlite:///{db_path}", echo=False)
    return AdminUserManagementService(
        engine=engine,
        session_factory=build_session_factory(engine),
        password_hasher=lambda password: f"hashed:{password}",
    )


def _create_store_admin(service: AdminUserManagementService) -> str:
    result = service.create_store_with_admin(
        store_code="LAN",
        store_name="Language Store",
        address="Pune",
        city="Pune",
        manager_name="Store Lead",
        contact_info="9999999999 | store@example.com",
        owner_name="Owner",
        owner_mobile="9999999999",
        owner_email="owner@example.com",
        status="Active",
        store_admin_username="language-admin",
        store_admin_full_name="Language Admin",
        store_admin_mobile="9999999999",
        store_admin_email="admin@example.com",
    )
    assert result.store_admin_user_id is not None
    return result.store_admin_user_id


def test_manager_language_defaults_to_english_and_updates_for_store_admin(tmp_path) -> None:
    service = _build_service(tmp_path)
    store_admin_user_id = _create_store_admin(service)

    context = service.get_store_dashboard_context_for_user(store_admin_user_id)

    assert context is not None
    assert context.manager_language_code == "en"

    updated_context = service.update_manager_language_for_store_admin(
        actor_user_id=store_admin_user_id,
        language_code="mr",
    )

    assert updated_context.manager_language_code == "mr"
    assert (
        service.get_store_dashboard_context_for_user(store_admin_user_id).manager_language_code
        == "mr"
    )


def test_manager_language_update_rejects_non_admin_store_user(tmp_path) -> None:
    service = _build_service(tmp_path)
    store_admin_user_id = _create_store_admin(service)
    staff = service.create_staff_member(
        actor_user_id=store_admin_user_id,
        username="manager-user",
        full_name="Manager User",
        contact_number="8888888888",
        speciality="Orders",
        joining_date=datetime(2026, 4, 26, tzinfo=timezone.utc),
        role_name="Manager",
    )

    with pytest.raises(ValueError, match="Only the store admin"):
        service.update_manager_language_for_store_admin(
            actor_user_id=staff.user_id,
            language_code="hi",
        )
