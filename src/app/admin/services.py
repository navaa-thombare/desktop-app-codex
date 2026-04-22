from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, inspect, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class ManagedUserModel(Base):
    __tablename__ = "managed_users"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_info: Mapped[str] = mapped_column(String(200), nullable=False)
    store_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    speciality: Mapped[str | None] = mapped_column(String(150), nullable=True)
    joining_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    roles: Mapped[list["ManagedUserRoleModel"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    permissions: Mapped[list["ManagedUserPermissionModel"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    activities: Mapped[list["ManagedUserActivityModel"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_record: Mapped["ManagedUserAuthModel | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ManagedUserRoleModel(Base):
    __tablename__ = "managed_user_roles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("managed_users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_name: Mapped[str] = mapped_column(String(120), primary_key=True)

    user: Mapped[ManagedUserModel] = relationship(back_populates="roles")


class ManagedUserPermissionModel(Base):
    __tablename__ = "managed_user_permissions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("managed_users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_name: Mapped[str] = mapped_column(String(120), primary_key=True)

    user: Mapped[ManagedUserModel] = relationship(back_populates="permissions")


class ManagedStoreModel(Base):
    __tablename__ = "managed_stores"

    store_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    store_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    store_name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(250), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    manager_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_info: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    owner_mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    owner_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    store_admin_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ManagedRoleDefinitionModel(Base):
    __tablename__ = "managed_role_definitions"

    role_name: Mapped[str] = mapped_column(String(120), primary_key=True)
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    permission_blob: Mapped[str] = mapped_column(String(1600), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ManagedUserActivityModel(Base):
    __tablename__ = "managed_user_activities"

    activity_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("managed_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(String(240), nullable=False)

    user: Mapped[ManagedUserModel] = relationship(back_populates="activities")


class ManagedUserAuthModel(Base):
    __tablename__ = "managed_user_auth"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("managed_users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lockout_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[ManagedUserModel] = relationship(back_populates="auth_record")


@dataclass(frozen=True)
class AdminUserSummary:
    user_id: str
    full_name: str


@dataclass(frozen=True)
class AdminUserActivity:
    occurred_at: datetime
    summary: str


@dataclass(frozen=True)
class AdminUserProfile:
    user_id: str
    full_name: str
    username: str
    contact_info: str
    store_id: str | None
    store_name: str
    created_on: datetime
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    activities: tuple[AdminUserActivity, ...]


@dataclass(frozen=True)
class StoreStaffRow:
    user_id: str
    full_name: str
    contact_number: str
    speciality: str
    joining_date: datetime
    role_name: str
    username: str
    created_by_name: str


@dataclass(frozen=True)
class StaffMemberProfile:
    user_id: str | None
    full_name: str
    contact_number: str
    speciality: str
    joining_date: datetime
    role_name: str
    username: str
    created_by_user_id: str | None
    created_by_name: str


@dataclass(frozen=True)
class StaffMemberSaveResult:
    user_id: str
    username: str
    temporary_password: str | None = None


@dataclass(frozen=True)
class AdminStoreRecord:
    store_id: str
    store_code: str
    store_name: str
    address: str
    city: str
    manager_name: str
    contact_info: str
    owner_name: str
    owner_mobile: str
    owner_email: str
    store_admin_user_id: str | None
    store_admin_username: str
    store_admin_full_name: str
    store_admin_mobile: str
    store_admin_email: str
    status: str
    created_on: datetime
    updated_on: datetime


@dataclass(frozen=True)
class StoreProvisionResult:
    store_id: str
    store_admin_user_id: str | None
    store_admin_username: str | None
    temporary_password: str | None = None


@dataclass(frozen=True)
class StoreDashboardContext:
    store_id: str
    store_code: str
    store_name: str
    address: str
    city: str
    contact_info: str
    owner_name: str
    owner_mobile: str
    owner_email: str
    status: str
    user_count: int


@dataclass(frozen=True)
class AdminRoleDefinition:
    role_name: str
    scope: str
    description: str
    permissions: tuple[str, ...]
    is_active: bool
    created_on: datetime
    updated_on: datetime


class AdminUserManagementService:
    ROLE_OPTIONS = (
        "Superadmin",
        "Admin",
        "Manager",
        "Worker",
    )
    ROLE_PERMISSION_MAP = {
        "Superadmin": (
            "nav:home",
            "nav:admin",
            "nav:operations",
            "report:run",
            "store:view",
            "store:create",
            "store:update",
            "store:activate",
            "store:deactivate",
            "user:view",
            "user:create:admin",
            "user:create:store_admin",
            "user:create:staff",
            "user:edit",
            "user:update:store_admin",
            "user:delete:store_admin",
            "user:activate:store_admin",
            "user:deactivate:store_admin",
            "role:view",
            "role:create",
            "role:update",
            "permission:view",
            "permission:add",
            "permission:remove",
            "customer:create",
            "customer:update",
            "order:view",
            "order:create",
            "order:update",
            "order:status:new",
            "order:status:waiting",
            "order:status:inprogress",
            "order:status:hold",
            "order:status:ready",
            "order:status:delivered",
            "order:status:canceled",
            "order:status:fulfilled",
            "billing:view",
            "billing:update",
        ),
        "Admin": (
            "nav:home",
            "nav:admin",
            "user:view",
            "user:create:staff",
            "user:edit",
        ),
        "Manager": (
            "nav:home",
            "nav:operations",
            "customer:create",
            "customer:update",
            "order:view",
            "order:create",
            "order:update",
            "order:status:new",
            "order:status:waiting",
            "order:status:inprogress",
            "order:status:hold",
            "order:status:ready",
            "order:status:delivered",
            "order:status:canceled",
            "order:status:fulfilled",
            "billing:view",
            "billing:update",
        ),
        "Worker": (
            "nav:home",
            "nav:operations",
            "order:view",
            "order:status:inprogress",
            "order:status:hold",
            "order:status:ready",
        ),
    }
    PERMISSION_OPTIONS = tuple(
        dict.fromkeys(
            permission
            for permissions in ROLE_PERMISSION_MAP.values()
            for permission in permissions
        )
    )
    MANAGER_ORDER_STATUSES = (
        "NEW",
        "WAITING",
        "INPROGRESS",
        "HOLD",
        "READY",
        "DELIVERED",
        "CANCELED",
        "FULFILLED",
    )
    WORKER_ORDER_STATUSES = (
        "INPROGRESS",
        "HOLD",
        "READY",
    )
    STORE_STATUS_OPTIONS = ("Active", "Inactive")
    CREATOR_ROLE_SCOPE = {
        "Superadmin": ("Admin", "Manager", "Worker"),
        "Admin": ("Manager", "Worker"),
        "Manager": (),
        "Worker": (),
    }
    ROLE_SCOPE_MAP = {
        "Superadmin": "Global",
        "Admin": "Administration",
        "Manager": "Operations",
        "Worker": "Operations",
    }
    ROLE_DESCRIPTION_MAP = {
        "Superadmin": "Full application control, including store lifecycle management, store-admin management, role creation, and permission administration.",
        "Admin": "Manages non-superadmin users and administrative workflows.",
        "Manager": "Handles customers, orders, billing updates, and fulfillment changes.",
        "Worker": "Reads order details and updates in-progress operational statuses.",
    }

    def __init__(
        self,
        *,
        engine,
        session_factory: sessionmaker[Session],
        password_hasher: Callable[[str], str],
        bootstrap_password: str = "ChangeMe123!",
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory
        self._password_hasher = password_hasher
        self._bootstrap_password = bootstrap_password
        Base.metadata.create_all(bind=self._engine)
        self._ensure_user_schema_columns()
        self._ensure_store_schema_columns()
        self._seed_if_needed()
        self._ensure_default_hierarchy_users()
        self._ensure_role_definitions()
        self._ensure_store_catalog()
        self._backfill_store_metadata()
        self._backfill_store_user_assignments()
        self._ensure_auth_records()
        self._backfill_staff_metadata()

    def list_users(
        self,
        *,
        actor_user_id: str | None = None,
        store_id: str | None = None,
    ) -> tuple[AdminUserSummary, ...]:
        scoped_store_id = self._resolve_store_scope(
            actor_user_id=actor_user_id,
            explicit_store_id=store_id,
        )
        actor_role = self.role_name_for_user(actor_user_id)
        manageable_roles = set(self.available_roles_for_actor(actor_user_id))
        with self._session_factory() as session:
            statement = select(ManagedUserModel)
            if scoped_store_id is not None and actor_role != "Superadmin":
                statement = statement.where(ManagedUserModel.store_id == scoped_store_id)
            rows = session.scalars(statement.order_by(ManagedUserModel.full_name.asc())).all()
            if scoped_store_id is not None and actor_role != "Superadmin":
                rows = [
                    row
                    for row in rows
                    if row.user_id != actor_user_id
                    and self._normalized_role_for_existing_user(row) in manageable_roles
                ]
            return tuple(AdminUserSummary(user_id=row.user_id, full_name=row.full_name) for row in rows)

    def list_stores(self) -> tuple[AdminStoreRecord, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ManagedStoreModel).order_by(
                    ManagedStoreModel.status.asc(),
                    ManagedStoreModel.store_name.asc(),
                )
            ).all()
            return tuple(self._to_store_record(row, session=session) for row in rows)

    def get_store(self, store_id: str) -> AdminStoreRecord | None:
        with self._session_factory() as session:
            row = session.get(ManagedStoreModel, store_id)
            if row is None:
                return None
            return self._to_store_record(row, session=session)

    def create_store(
        self,
        *,
        store_code: str,
        store_name: str,
        address: str,
        city: str,
        manager_name: str,
        contact_info: str,
        status: str,
    ) -> str:
        normalized_store = self._normalize_store_fields(
            store_code=store_code,
            store_name=store_name,
            address=address,
            city=city,
            manager_name=manager_name,
            contact_info=contact_info,
            status=status,
        )

        with self._session_factory() as session:
            existing_store = session.scalar(
                select(ManagedStoreModel).where(
                    ManagedStoreModel.store_code == normalized_store["store_code"]
                )
            )
            if existing_store is not None:
                raise ValueError(f"Store code '{normalized_store['store_code']}' already exists.")

            now = datetime.now(tz=timezone.utc)
            store_id = f"store-{uuid4().hex[:8]}"
            store = ManagedStoreModel(
                store_id=store_id,
                store_code=normalized_store["store_code"],
                store_name=normalized_store["store_name"],
                address=normalized_store["address"],
                city=normalized_store["city"],
                manager_name=normalized_store["manager_name"],
                contact_info=normalized_store["contact_info"],
                owner_name=normalized_store["manager_name"],
                owner_mobile=self._extract_mobile(normalized_store["contact_info"]),
                owner_email=self._extract_email(normalized_store["contact_info"]),
                status=normalized_store["status"],
                created_on=now,
                updated_on=now,
            )
            session.add(store)
            session.commit()
            return store_id

    def update_store(
        self,
        *,
        store_id: str,
        store_code: str,
        store_name: str,
        address: str,
        city: str,
        manager_name: str,
        contact_info: str,
        status: str,
    ) -> None:
        normalized_store = self._normalize_store_fields(
            store_code=store_code,
            store_name=store_name,
            address=address,
            city=city,
            manager_name=manager_name,
            contact_info=contact_info,
            status=status,
        )

        with self._session_factory() as session:
            store = session.get(ManagedStoreModel, store_id)
            if store is None:
                raise ValueError(f"Unknown store: {store_id}")

            duplicate_store = session.scalar(
                select(ManagedStoreModel).where(
                    ManagedStoreModel.store_code == normalized_store["store_code"],
                    ManagedStoreModel.store_id != store_id,
                )
            )
            if duplicate_store is not None:
                raise ValueError(f"Store code '{normalized_store['store_code']}' already exists.")

            store.store_code = normalized_store["store_code"]
            store.store_name = normalized_store["store_name"]
            store.address = normalized_store["address"]
            store.city = normalized_store["city"]
            store.manager_name = normalized_store["manager_name"]
            store.contact_info = normalized_store["contact_info"]
            store.status = normalized_store["status"]
            if not store.owner_name:
                store.owner_name = normalized_store["manager_name"]
            if not store.owner_mobile:
                store.owner_mobile = self._extract_mobile(normalized_store["contact_info"])
            if not store.owner_email:
                store.owner_email = self._extract_email(normalized_store["contact_info"])
            store.updated_on = datetime.now(tz=timezone.utc)
            session.commit()

    def create_store_with_admin(
        self,
        *,
        store_code: str,
        store_name: str,
        address: str,
        city: str,
        manager_name: str,
        contact_info: str,
        owner_name: str,
        owner_mobile: str,
        owner_email: str,
        status: str,
        store_admin_username: str,
        store_admin_full_name: str,
        store_admin_mobile: str,
        store_admin_email: str,
    ) -> StoreProvisionResult:
        normalized_store = self._normalize_store_fields(
            store_code=store_code,
            store_name=store_name,
            address=address,
            city=city,
            manager_name=manager_name,
            contact_info=contact_info,
            status=status,
        )
        normalized_owner = self._normalize_owner_fields(
            owner_name=owner_name,
            owner_mobile=owner_mobile,
            owner_email=owner_email,
        )
        normalized_admin = self._normalize_store_admin_fields(
            username=store_admin_username,
            full_name=store_admin_full_name,
            mobile=store_admin_mobile,
            email=store_admin_email,
            require_all_fields=True,
        )

        with self._session_factory() as session:
            existing_store = session.scalar(
                select(ManagedStoreModel).where(
                    ManagedStoreModel.store_code == normalized_store["store_code"]
                )
            )
            if existing_store is not None:
                raise ValueError(f"Store code '{normalized_store['store_code']}' already exists.")

            existing_admin = session.scalar(
                select(ManagedUserModel).where(
                    ManagedUserModel.username == normalized_admin["username"]
                )
            )
            if existing_admin is not None:
                raise ValueError(
                    f"Username '{normalized_admin['username']}' already exists for the store admin user."
                )

            now = datetime.now(tz=timezone.utc)
            store_id = f"store-{uuid4().hex[:8]}"
            store_admin_user_id = f"u-store-admin-{uuid4().hex[:8]}"
            temporary_password = self.default_password_for_username(normalized_admin["username"])
            store = ManagedStoreModel(
                store_id=store_id,
                store_code=normalized_store["store_code"],
                store_name=normalized_store["store_name"],
                address=normalized_store["address"],
                city=normalized_store["city"],
                manager_name=normalized_store["manager_name"],
                contact_info=normalized_store["contact_info"],
                owner_name=normalized_owner["owner_name"],
                owner_mobile=normalized_owner["owner_mobile"],
                owner_email=normalized_owner["owner_email"],
                store_admin_user_id=store_admin_user_id,
                status=normalized_store["status"],
                created_on=now,
                updated_on=now,
            )
            session.add(store)

            admin_user = self._build_user(
                user_id=store_admin_user_id,
                username=normalized_admin["username"],
                full_name=normalized_admin["full_name"],
                contact_info=self._compose_contact_info(
                    mobile=normalized_admin["mobile"],
                    email=normalized_admin["email"],
                ),
                store_id=store_id,
                created_on=now,
                roles=["Admin"],
                permissions=self._permissions_for_selected_role("Admin"),
                activities=[
                    (now, f"Store admin account created for {normalized_store['store_name']}"),
                ],
            )
            admin_user.auth_record = ManagedUserAuthModel(
                user_id=store_admin_user_id,
                mobile=normalized_admin["mobile"],
                password_hash=self._password_hasher(temporary_password),
                failed_attempts=0,
                lockout_until=None,
                password_reset_required=True,
            )
            session.add(admin_user)
            session.commit()
            return StoreProvisionResult(
                store_id=store_id,
                store_admin_user_id=store_admin_user_id,
                store_admin_username=normalized_admin["username"],
                temporary_password=temporary_password,
            )

    def update_store_with_admin(
        self,
        *,
        store_id: str,
        store_code: str,
        store_name: str,
        address: str,
        city: str,
        manager_name: str,
        contact_info: str,
        owner_name: str,
        owner_mobile: str,
        owner_email: str,
        status: str,
        store_admin_username: str,
        store_admin_full_name: str,
        store_admin_mobile: str,
        store_admin_email: str,
    ) -> StoreProvisionResult:
        normalized_store = self._normalize_store_fields(
            store_code=store_code,
            store_name=store_name,
            address=address,
            city=city,
            manager_name=manager_name,
            contact_info=contact_info,
            status=status,
        )
        normalized_owner = self._normalize_owner_fields(
            owner_name=owner_name,
            owner_mobile=owner_mobile,
            owner_email=owner_email,
        )

        with self._session_factory() as session:
            store = session.get(ManagedStoreModel, store_id)
            if store is None:
                raise ValueError(f"Unknown store: {store_id}")

            duplicate_store = session.scalar(
                select(ManagedStoreModel).where(
                    ManagedStoreModel.store_code == normalized_store["store_code"],
                    ManagedStoreModel.store_id != store_id,
                )
            )
            if duplicate_store is not None:
                raise ValueError(f"Store code '{normalized_store['store_code']}' already exists.")

            store.store_code = normalized_store["store_code"]
            store.store_name = normalized_store["store_name"]
            store.address = normalized_store["address"]
            store.city = normalized_store["city"]
            store.manager_name = normalized_store["manager_name"]
            store.contact_info = normalized_store["contact_info"]
            store.owner_name = normalized_owner["owner_name"]
            store.owner_mobile = normalized_owner["owner_mobile"]
            store.owner_email = normalized_owner["owner_email"]
            store.status = normalized_store["status"]

            linked_admin = (
                session.get(ManagedUserModel, store.store_admin_user_id)
                if store.store_admin_user_id
                else None
            )
            created_password: str | None = None

            if linked_admin is None:
                normalized_admin = self._normalize_store_admin_fields(
                    username=store_admin_username,
                    full_name=store_admin_full_name,
                    mobile=store_admin_mobile,
                    email=store_admin_email,
                    require_all_fields=False,
                )
                if normalized_admin is not None:
                    existing_admin = session.scalar(
                        select(ManagedUserModel).where(
                            ManagedUserModel.username == normalized_admin["username"]
                        )
                    )
                    if existing_admin is not None:
                        raise ValueError(
                            f"Username '{normalized_admin['username']}' already exists for the store admin user."
                        )
                    now = datetime.now(tz=timezone.utc)
                    store.store_admin_user_id = f"u-store-admin-{uuid4().hex[:8]}"
                    created_password = self.default_password_for_username(
                        normalized_admin["username"]
                    )
                    admin_user = self._build_user(
                        user_id=store.store_admin_user_id,
                        username=normalized_admin["username"],
                        full_name=normalized_admin["full_name"],
                        contact_info=self._compose_contact_info(
                            mobile=normalized_admin["mobile"],
                            email=normalized_admin["email"],
                        ),
                        store_id=store.store_id,
                        created_on=now,
                        roles=["Admin"],
                        permissions=self._permissions_for_selected_role("Admin"),
                        activities=[
                            (now, f"Store admin account created for {normalized_store['store_name']}"),
                        ],
                    )
                    admin_user.auth_record = ManagedUserAuthModel(
                        user_id=store.store_admin_user_id,
                        mobile=normalized_admin["mobile"],
                        password_hash=self._password_hasher(created_password),
                        failed_attempts=0,
                        lockout_until=None,
                        password_reset_required=True,
                    )
                    session.add(admin_user)
                    linked_admin = admin_user
            else:
                normalized_admin = self._normalize_store_admin_fields(
                    username=linked_admin.username,
                    full_name=store_admin_full_name,
                    mobile=store_admin_mobile,
                    email=store_admin_email,
                    require_all_fields=True,
                )
                linked_admin.full_name = normalized_admin["full_name"]
                linked_admin.store_id = store.store_id
                linked_admin.contact_info = self._compose_contact_info(
                    mobile=normalized_admin["mobile"],
                    email=normalized_admin["email"],
                )
                linked_admin.roles[:] = [
                    ManagedUserRoleModel(user_id=linked_admin.user_id, role_name="Admin")
                ]
                linked_admin.permissions[:] = [
                    ManagedUserPermissionModel(
                        user_id=linked_admin.user_id,
                        permission_name=permission_name,
                    )
                    for permission_name in self._permissions_for_selected_role("Admin")
                ]
                linked_admin.activities.insert(
                    0,
                    ManagedUserActivityModel(
                        user_id=linked_admin.user_id,
                        occurred_at=datetime.now(tz=timezone.utc),
                        summary=f"Store admin details updated for {normalized_store['store_name']}",
                    ),
                )
                if linked_admin.auth_record is not None:
                    linked_admin.auth_record.mobile = normalized_admin["mobile"]

            store.updated_on = datetime.now(tz=timezone.utc)
            session.commit()
            return StoreProvisionResult(
                store_id=store.store_id,
                store_admin_user_id=store.store_admin_user_id,
                store_admin_username=linked_admin.username if linked_admin is not None else None,
                temporary_password=created_password,
            )

    def list_role_definitions(self) -> tuple[AdminRoleDefinition, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ManagedRoleDefinitionModel).order_by(
                    ManagedRoleDefinitionModel.role_name.asc()
                )
            ).all()
            ordered_rows = sorted(
                rows,
                key=lambda row: (
                    self._role_sort_key(row.role_name),
                    row.role_name.lower(),
                ),
            )
            return tuple(self._to_role_definition(row) for row in ordered_rows)

    def get_role_definition(self, role_name: str) -> AdminRoleDefinition | None:
        normalized_role_name = role_name.strip()
        if not normalized_role_name:
            return None

        with self._session_factory() as session:
            row = session.get(ManagedRoleDefinitionModel, normalized_role_name)
            if row is None:
                return None
            return self._to_role_definition(row)

    def create_role_definition(
        self,
        *,
        role_name: str,
        scope: str,
        description: str,
        permissions: list[str],
        is_active: bool,
    ) -> str:
        normalized_role_name = role_name.strip()
        normalized_scope = scope.strip()
        normalized_description = description.strip()
        normalized_permissions = self._normalize_permission_values(permissions)
        if not normalized_role_name:
            raise ValueError("Role name is required.")
        if not normalized_scope:
            raise ValueError("Scope is required.")
        if not normalized_description:
            raise ValueError("Description is required.")
        if not normalized_permissions:
            raise ValueError("At least one permission is required.")

        with self._session_factory() as session:
            existing_role = session.get(ManagedRoleDefinitionModel, normalized_role_name)
            if existing_role is not None:
                raise ValueError(f"Role '{normalized_role_name}' already exists.")

            now = datetime.now(tz=timezone.utc)
            row = ManagedRoleDefinitionModel(
                role_name=normalized_role_name,
                scope=normalized_scope,
                description=normalized_description,
                permission_blob=self._serialize_permissions(normalized_permissions),
                is_active=is_active,
                created_on=now,
                updated_on=now,
            )
            session.add(row)
            session.commit()
            return normalized_role_name

    def update_role_definition(
        self,
        *,
        role_name: str,
        scope: str,
        description: str,
        permissions: list[str],
        is_active: bool,
    ) -> None:
        normalized_role_name = role_name.strip()
        normalized_scope = scope.strip()
        normalized_description = description.strip()
        normalized_permissions = self._normalize_permission_values(permissions)
        if not normalized_role_name:
            raise ValueError("Role name is required.")
        if not normalized_scope:
            raise ValueError("Scope is required.")
        if not normalized_description:
            raise ValueError("Description is required.")
        if not normalized_permissions:
            raise ValueError("At least one permission is required.")

        with self._session_factory() as session:
            row = session.get(ManagedRoleDefinitionModel, normalized_role_name)
            if row is None:
                raise ValueError(f"Unknown role definition: {normalized_role_name}")

            row.scope = normalized_scope
            row.description = normalized_description
            row.permission_blob = self._serialize_permissions(normalized_permissions)
            row.is_active = is_active
            row.updated_on = datetime.now(tz=timezone.utc)
            session.commit()

    def role_name_for_user(self, user_id: str | None) -> str | None:
        if user_id is None:
            return None

        profile = self.get_user_profile(user_id)
        if profile is None or not profile.roles:
            return None
        return profile.roles[0]

    def permissions_for_role(self, role_name: str) -> tuple[str, ...]:
        role_definition = self.get_role_definition(role_name)
        if role_definition is not None:
            return role_definition.permissions
        return self.ROLE_PERMISSION_MAP.get(role_name, ())

    def available_roles_for_actor(self, actor_user_id: str | None) -> tuple[str, ...]:
        actor_role = self.role_name_for_user(actor_user_id)
        if actor_role is None:
            return ()
        return self.CREATOR_ROLE_SCOPE.get(actor_role, ())

    def can_actor_create_users(self, actor_user_id: str | None) -> bool:
        return bool(self.available_roles_for_actor(actor_user_id))

    def can_actor_manage_user(self, actor_user_id: str | None, target_user_id: str | None) -> bool:
        actor_role = self.role_name_for_user(actor_user_id)
        target_role = self.role_name_for_user(target_user_id)
        if actor_role is None or target_role is None:
            return False
        if actor_role != "Superadmin":
            actor_store_id = self.store_id_for_user(actor_user_id)
            target_store_id = self.store_id_for_user(target_user_id)
            if not actor_store_id or actor_store_id != target_store_id:
                return False
        return target_role in self.CREATOR_ROLE_SCOPE.get(actor_role, ())

    def store_id_for_user(self, user_id: str | None) -> str | None:
        if user_id is None:
            return None

        with self._session_factory() as session:
            user = session.get(ManagedUserModel, user_id)
            if user is None:
                return None
            return user.store_id

    def get_store_for_user(self, user_id: str | None) -> AdminStoreRecord | None:
        store_id = self.store_id_for_user(user_id)
        if store_id is None:
            return None
        return self.get_store(store_id)

    def display_name_for_user(self, user_id: str | None) -> str:
        if user_id is None:
            return ""
        with self._session_factory() as session:
            user = session.get(ManagedUserModel, user_id)
            return user.full_name if user is not None else ""

    def list_store_staff(
        self,
        *,
        actor_user_id: str | None,
        created_by_actor_only: bool = False,
    ) -> tuple[StoreStaffRow, ...]:
        store_id = self.store_id_for_user(actor_user_id)
        if store_id is None:
            return ()

        with self._session_factory() as session:
            rows = session.scalars(
                select(ManagedUserModel)
                .where(ManagedUserModel.store_id == store_id)
                .order_by(ManagedUserModel.full_name.asc())
            ).all()
            actor_role = self.role_name_for_user(actor_user_id)
            allowed_roles = set(self.available_roles_for_actor(actor_user_id))
            creator_lookup = {
                user.user_id: user.full_name
                for user in session.scalars(select(ManagedUserModel)).all()
            }
            return tuple(
                StoreStaffRow(
                    user_id=row.user_id,
                    full_name=row.full_name,
                    contact_number=self._contact_number_for_user(row),
                    speciality=(row.speciality or "").strip(),
                    joining_date=self._ensure_utc(row.joining_date or row.created_on),
                    role_name=self._normalized_role_for_existing_user(row),
                    username=row.username,
                    created_by_name=creator_lookup.get(row.created_by_user_id or "", ""),
                )
                for row in rows
                if (
                    (actor_role == "Superadmin" or row.user_id != actor_user_id)
                    and (
                        actor_role == "Superadmin"
                        or self._normalized_role_for_existing_user(row) in allowed_roles
                    )
                    and (
                        not created_by_actor_only
                        or actor_user_id is None
                        or row.created_by_user_id == actor_user_id
                    )
                )
            )

    def get_staff_member_profile(
        self,
        *,
        actor_user_id: str | None,
        user_id: str,
    ) -> StaffMemberProfile | None:
        with self._session_factory() as session:
            user = session.get(ManagedUserModel, user_id)
            if user is None:
                return None
            self._assert_staff_manageable(
                actor_user_id=actor_user_id,
                target_user=user,
                require_creator_match=True,
            )
            return StaffMemberProfile(
                user_id=user.user_id,
                full_name=user.full_name,
                contact_number=self._contact_number_for_user(user),
                speciality=(user.speciality or "").strip(),
                joining_date=self._ensure_utc(user.joining_date or user.created_on),
                role_name=self._normalized_role_for_existing_user(user),
                username=user.username,
                created_by_user_id=user.created_by_user_id,
                created_by_name=self._creator_name_for_user(session=session, user=user),
            )

    def create_staff_member(
        self,
        *,
        actor_user_id: str | None,
        username: str,
        full_name: str,
        contact_number: str,
        speciality: str,
        joining_date: datetime,
        role_name: str,
    ) -> StaffMemberSaveResult:
        actor_role = self.role_name_for_user(actor_user_id)
        if actor_role != "Admin":
            raise ValueError("Only store admin users can create store staff.")

        normalized_username = self._normalize_managed_username(username)
        normalized_full_name = self._normalize_required_value(
            full_name,
            "Full name is required before a staff member can be created.",
        )
        normalized_contact_number = self._normalize_required_value(
            contact_number,
            "Contact number is required before a staff member can be created.",
        )
        normalized_speciality = speciality.strip()
        normalized_joining_date = self._normalize_joining_date(joining_date)
        selected_role = self._normalize_staff_role_for_actor(
            actor_user_id=actor_user_id,
            role_name=role_name,
        )
        store_scope_id = self._resolve_store_scope(actor_user_id=actor_user_id)
        temporary_password = self.default_password_for_username(normalized_username)

        with self._session_factory() as session:
            existing_user = session.scalar(
                select(ManagedUserModel).where(ManagedUserModel.username == normalized_username)
            )
            if existing_user is not None:
                raise ValueError(f"Username '{normalized_username}' already exists.")

            created_on = datetime.now(tz=timezone.utc)
            user_id = f"u-managed-{uuid4().hex[:8]}"
            user = self._build_user(
                user_id=user_id,
                username=normalized_username,
                full_name=normalized_full_name,
                contact_info=normalized_contact_number,
                store_id=store_scope_id,
                created_on=created_on,
                roles=[selected_role],
                permissions=self._permissions_for_selected_role(selected_role),
                activities=[
                    (
                        created_on,
                        f"Staff member created by {self.display_name_for_user(actor_user_id) or 'Store Admin'}",
                    ),
                ],
                speciality=normalized_speciality,
                joining_date=normalized_joining_date,
                created_by_user_id=actor_user_id,
            )
            user.auth_record = ManagedUserAuthModel(
                user_id=user_id,
                mobile=normalized_contact_number,
                password_hash=self._password_hasher(temporary_password),
                failed_attempts=0,
                lockout_until=None,
                password_reset_required=True,
            )
            session.add(user)
            session.commit()
            return StaffMemberSaveResult(
                user_id=user_id,
                username=normalized_username,
                temporary_password=temporary_password,
            )

    def update_staff_member(
        self,
        *,
        actor_user_id: str | None,
        user_id: str,
        full_name: str,
        contact_number: str,
        speciality: str,
        joining_date: datetime,
        role_name: str,
    ) -> StaffMemberSaveResult:
        normalized_full_name = self._normalize_required_value(
            full_name,
            "Full name is required before a staff member can be updated.",
        )
        normalized_contact_number = self._normalize_required_value(
            contact_number,
            "Contact number is required before a staff member can be updated.",
        )
        normalized_speciality = speciality.strip()
        normalized_joining_date = self._normalize_joining_date(joining_date)
        selected_role = self._normalize_staff_role_for_actor(
            actor_user_id=actor_user_id,
            role_name=role_name,
        )

        with self._session_factory() as session:
            user = session.get(ManagedUserModel, user_id)
            if user is None:
                raise ValueError("The selected staff member no longer exists.")
            self._assert_staff_manageable(
                actor_user_id=actor_user_id,
                target_user=user,
                require_creator_match=True,
            )

            user.full_name = normalized_full_name
            user.contact_info = normalized_contact_number
            user.speciality = normalized_speciality
            user.joining_date = normalized_joining_date
            user.roles[:] = [
                ManagedUserRoleModel(user_id=user.user_id, role_name=selected_role)
            ]
            user.permissions[:] = [
                ManagedUserPermissionModel(
                    user_id=user.user_id,
                    permission_name=permission_name,
                )
                for permission_name in self._permissions_for_selected_role(selected_role)
            ]
            if user.auth_record is not None:
                user.auth_record.mobile = normalized_contact_number
            user.activities.append(
                ManagedUserActivityModel(
                    user_id=user.user_id,
                    occurred_at=datetime.now(tz=timezone.utc),
                    summary=f"Staff member updated by {self.display_name_for_user(actor_user_id) or 'Store Admin'}",
                )
            )
            session.commit()
            return StaffMemberSaveResult(user_id=user.user_id, username=user.username)

    def get_store_dashboard_context_for_user(
        self,
        user_id: str | None,
    ) -> StoreDashboardContext | None:
        store_id = self.store_id_for_user(user_id)
        if store_id is None:
            return None

        with self._session_factory() as session:
            store = session.get(ManagedStoreModel, store_id)
            if store is None:
                return None
            user_count = session.scalar(
                select(func.count()).select_from(ManagedUserModel).where(
                    ManagedUserModel.store_id == store_id
                )
            ) or 0
            return StoreDashboardContext(
                store_id=store.store_id,
                store_code=store.store_code,
                store_name=store.store_name,
                address=store.address or "",
                city=store.city,
                contact_info=store.contact_info,
                owner_name=store.owner_name or "",
                owner_mobile=store.owner_mobile or "",
                owner_email=store.owner_email or "",
                status=store.status,
                user_count=int(user_count),
            )

    def update_store_profile_for_user(
        self,
        *,
        actor_user_id: str | None,
        address: str,
        contact_info: str,
    ) -> AdminStoreRecord:
        store_id = self.store_id_for_user(actor_user_id)
        actor_role = self.role_name_for_user(actor_user_id)
        if not store_id:
            raise ValueError("This account is not linked to a store profile.")
        if actor_role != "Admin":
            raise ValueError("Only the store admin can update store profile details here.")

        normalized_address = address.strip()
        normalized_contact_info = contact_info.strip()
        if not normalized_address:
            raise ValueError("Store address is required.")
        if not normalized_contact_info:
            raise ValueError("Store contact information is required.")

        with self._session_factory() as session:
            store = session.get(ManagedStoreModel, store_id)
            if store is None:
                raise ValueError("The linked store record was not found.")
            if store.store_admin_user_id != actor_user_id:
                raise ValueError("Only the linked store admin can update this store profile.")

            store.address = normalized_address
            store.contact_info = normalized_contact_info
            store.updated_on = datetime.now(tz=timezone.utc)
            session.commit()
            session.refresh(store)
            return self._to_store_record(store, session=session)

    def reset_to_superadmin_only(self) -> None:
        with self._session_factory() as session:
            now = datetime.now(tz=timezone.utc)
            superadmin = session.scalar(
                select(ManagedUserModel).where(ManagedUserModel.username == "superadmin")
            )
            if superadmin is None:
                superadmin = self._build_superadmin_user(
                    user_id=f"u-superadmin-{uuid4().hex[:6]}",
                    created_on=now - timedelta(days=1),
                    activity_summary="Superadmin account recreated during environment reset",
                )
                session.add(superadmin)
                session.flush()

            stores = session.scalars(select(ManagedStoreModel)).all()
            for store in stores:
                session.delete(store)

            users_to_delete = session.scalars(
                select(ManagedUserModel).where(ManagedUserModel.user_id != superadmin.user_id)
            ).all()
            for user in users_to_delete:
                session.delete(user)

            superadmin.full_name = superadmin.full_name.strip() or "Superadmin User"
            superadmin.contact_info = superadmin.contact_info.strip() or (
                "+15551230000 | superadmin@planning.local"
            )
            superadmin.store_id = None
            superadmin.roles[:] = [
                ManagedUserRoleModel(user_id=superadmin.user_id, role_name="Superadmin")
            ]
            superadmin.permissions[:] = [
                ManagedUserPermissionModel(
                    user_id=superadmin.user_id,
                    permission_name=permission_name,
                )
                for permission_name in self._permissions_for_selected_role("Superadmin")
            ]
            superadmin.activities[:] = [
                ManagedUserActivityModel(
                    user_id=superadmin.user_id,
                    occurred_at=now,
                    summary="Environment reset to superadmin-only baseline",
                )
            ]
            if superadmin.auth_record is None:
                superadmin.auth_record = ManagedUserAuthModel(
                    user_id=superadmin.user_id,
                    mobile=self._extract_mobile(superadmin.contact_info),
                    password_hash=self._password_hasher(
                        self.default_password_for_username("superadmin")
                    ),
                    failed_attempts=0,
                    lockout_until=None,
                    password_reset_required=False,
                )
            else:
                superadmin.auth_record.mobile = self._extract_mobile(superadmin.contact_info)
                superadmin.auth_record.failed_attempts = 0
                superadmin.auth_record.lockout_until = None
                superadmin.auth_record.password_reset_required = False

            session.commit()

    def default_password_for_username(self, username: str) -> str:
        normalized_username = username.strip().lower()
        return f"@ct{normalized_username}123456789"

    def get_user_profile(self, user_id: str) -> AdminUserProfile | None:
        with self._session_factory() as session:
            user = session.get(ManagedUserModel, user_id)
            if user is None:
                return None
            store = (
                session.get(ManagedStoreModel, user.store_id)
                if user.store_id
                else None
            )

            activities = sorted(
                (
                    AdminUserActivity(
                        occurred_at=self._ensure_utc(activity.occurred_at),
                        summary=activity.summary,
                    )
                    for activity in user.activities
                ),
                key=lambda item: item.occurred_at,
                reverse=True,
            )
            return AdminUserProfile(
                user_id=user.user_id,
                full_name=user.full_name,
                username=user.username,
                contact_info=user.contact_info,
                store_id=user.store_id,
                store_name=store.store_name if store is not None else "",
                created_on=self._ensure_utc(user.created_on),
                roles=self._ordered_role_names(tuple(role.role_name for role in user.roles)),
                permissions=tuple(
                    permission_name
                    for permission_name in self.permission_options()
                    if permission_name in {permission.permission_name for permission in user.permissions}
                ),
                activities=tuple(activities),
            )

    def save_user_profile(
        self,
        *,
        actor_user_id: str | None,
        user_id: str,
        full_name: str,
        contact_info: str,
        roles: list[str],
        permissions: list[str],
    ) -> None:
        if actor_user_id is not None and not self.can_actor_manage_user(actor_user_id, user_id):
            raise ValueError("This account cannot manage the selected user.")

        with self._session_factory() as session:
            user = session.get(ManagedUserModel, user_id)
            if user is None:
                raise ValueError(f"Unknown managed user: {user_id}")

            selected_role = self._normalize_role_selection(roles)
            allowed_roles = set(self.available_roles_for_actor(actor_user_id))
            actor_role = self.role_name_for_user(actor_user_id)
            if actor_user_id is not None and actor_role != "Superadmin" and selected_role not in allowed_roles:
                allowed_label = ", ".join(sorted(allowed_roles)) or "no roles"
                raise ValueError(f"This account can only assign these roles: {allowed_label}.")
            derived_permissions = self._permissions_for_selected_role(selected_role)
            user.full_name = full_name.strip()
            user.contact_info = contact_info.strip()
            if user.auth_record is not None:
                user.auth_record.mobile = self._extract_mobile(user.contact_info)
            user.roles[:] = [
                ManagedUserRoleModel(user_id=user.user_id, role_name=selected_role)
            ]
            user.permissions[:] = [
                ManagedUserPermissionModel(user_id=user.user_id, permission_name=permission_name)
                for permission_name in derived_permissions
            ]
            session.commit()

    def create_user(
        self,
        *,
        actor_user_id: str | None,
        username: str,
        full_name: str,
        contact_info: str,
        temporary_password: str,
        roles: list[str],
        permissions: list[str],
    ) -> str:
        normalized_username = username.strip().lower()
        normalized_full_name = full_name.strip()
        normalized_contact_info = contact_info.strip()
        if not normalized_username:
            raise ValueError("Username is required before a new user can be created.")
        if not normalized_full_name:
            raise ValueError("Name is required before a new user can be created.")
        if not normalized_contact_info:
            raise ValueError("Contact information is required before a new user can be created.")
        if not temporary_password:
            raise ValueError("A temporary password is required before a new user can be created.")

        selected_role = self._normalize_role_selection(roles)
        actor_role = self.role_name_for_user(actor_user_id)
        allowed_roles = set(self.available_roles_for_actor(actor_user_id))
        if actor_user_id is not None and actor_role != "Superadmin" and selected_role not in allowed_roles:
            allowed_label = ", ".join(sorted(allowed_roles)) or "no roles"
            raise ValueError(f"This account can only create these roles: {allowed_label}.")
        store_scope_id = self._resolve_store_scope(actor_user_id=actor_user_id)

        with self._session_factory() as session:
            existing_user = session.scalar(
                select(ManagedUserModel).where(ManagedUserModel.username == normalized_username)
            )
            if existing_user is not None:
                raise ValueError(f"Username '{normalized_username}' already exists.")

            created_on = datetime.now(tz=timezone.utc)
            user_id = f"u-managed-{uuid4().hex[:8]}"
            user = self._build_user(
                user_id=user_id,
                username=normalized_username,
                full_name=normalized_full_name,
                contact_info=normalized_contact_info,
                store_id=store_scope_id,
                created_on=created_on,
                roles=[selected_role],
                permissions=self._permissions_for_selected_role(selected_role),
                activities=[
                    (
                        created_on,
                        "User record created in admin console"
                        if store_scope_id is None
                        else f"User record created in store workspace ({store_scope_id})",
                    ),
                ],
                created_by_user_id=actor_user_id,
            )
            user.auth_record = ManagedUserAuthModel(
                user_id=user_id,
                mobile=self._extract_mobile(normalized_contact_info),
                password_hash=self._password_hasher(temporary_password),
                failed_attempts=0,
                lockout_until=None,
                password_reset_required=True,
            )
            session.add(user)
            session.commit()
            return user_id

    def role_options(self) -> tuple[str, ...]:
        definitions = self.list_role_definitions()
        active_role_names = tuple(
            definition.role_name
            for definition in definitions
            if definition.is_active
        )
        if active_role_names:
            return active_role_names
        return self.ROLE_OPTIONS

    def permission_options(self) -> tuple[str, ...]:
        ordered_permissions = dict.fromkeys(
            permission
            for definition in self.list_role_definitions()
            for permission in definition.permissions
        )
        if ordered_permissions:
            return tuple(ordered_permissions)
        return self.PERMISSION_OPTIONS

    def _seed_if_needed(self) -> None:
        with self._session_factory() as session:
            user_count = session.scalar(select(func.count()).select_from(ManagedUserModel)) or 0
            if user_count:
                return

            now = datetime.now(tz=timezone.utc)
            session.add(
                self._build_superadmin_user(
                    user_id="u-superadmin-1",
                    created_on=now - timedelta(days=90),
                    activity_summary="Created the initial superadmin account",
                )
            )
            session.commit()

    def _ensure_default_hierarchy_users(self) -> None:
        with self._session_factory() as session:
            existing_usernames = {
                username
                for username in session.scalars(select(ManagedUserModel.username)).all()
            }
            now = datetime.now(tz=timezone.utc)
            bootstrap_users: list[ManagedUserModel] = []
            if "superadmin" not in existing_usernames:
                bootstrap_users.append(
                    self._build_superadmin_user(
                        user_id=f"u-superadmin-{uuid4().hex[:6]}",
                        created_on=now - timedelta(days=90),
                        activity_summary="Bootstrap superadmin account created",
                    )
                )

            if bootstrap_users:
                session.add_all(bootstrap_users)
                session.commit()

    def _ensure_role_definitions(self) -> None:
        with self._session_factory() as session:
            now = datetime.now(tz=timezone.utc)
            data_updated = False
            for role_name in self.ROLE_OPTIONS:
                default_permissions = self.ROLE_PERMISSION_MAP.get(role_name, ())
                permission_blob = self._serialize_permissions(default_permissions)
                row = session.get(ManagedRoleDefinitionModel, role_name)
                if row is None:
                    session.add(
                        ManagedRoleDefinitionModel(
                            role_name=role_name,
                            scope=self.ROLE_SCOPE_MAP.get(role_name, "Operations"),
                            description=self.ROLE_DESCRIPTION_MAP.get(
                                role_name,
                                f"{role_name} role definition.",
                            ),
                            permission_blob=permission_blob,
                            is_active=True,
                            created_on=now,
                            updated_on=now,
                        )
                    )
                    data_updated = True
                    continue

                existing_permissions = self._deserialize_permissions(row.permission_blob)
                merged_permissions = tuple(
                    dict.fromkeys((*default_permissions, *existing_permissions))
                )
                merged_permission_blob = self._serialize_permissions(merged_permissions)
                if row.permission_blob != merged_permission_blob:
                    row.permission_blob = merged_permission_blob
                    row.updated_on = now
                    data_updated = True
                if not row.scope.strip():
                    row.scope = self.ROLE_SCOPE_MAP.get(role_name, "Operations")
                    row.updated_on = now
                    data_updated = True
                if not row.description.strip():
                    row.description = self.ROLE_DESCRIPTION_MAP.get(
                        role_name,
                        f"{role_name} role definition.",
                    )
                    row.updated_on = now
                    data_updated = True

            if data_updated:
                session.commit()

    def _ensure_store_catalog(self) -> None:
        return

    def _backfill_store_metadata(self) -> None:
        with self._session_factory() as session:
            stores = session.scalars(select(ManagedStoreModel)).all()
            updated = False
            for store in stores:
                if store.address is None:
                    store.address = ""
                    updated = True
                if not store.owner_name:
                    store.owner_name = store.manager_name
                    updated = True
                if not store.owner_mobile:
                    store.owner_mobile = self._extract_mobile(store.contact_info) or ""
                    updated = True
                if not store.owner_email:
                    store.owner_email = self._extract_email(store.contact_info) or ""
                    updated = True
            if updated:
                session.commit()

    def _backfill_store_user_assignments(self) -> None:
        with self._session_factory() as session:
            stores = session.scalars(select(ManagedStoreModel)).all()
            updated = False
            for store in stores:
                if not store.store_admin_user_id:
                    continue
                store_admin = session.get(ManagedUserModel, store.store_admin_user_id)
                if store_admin is None:
                    continue
                if store_admin.store_id != store.store_id:
                    store_admin.store_id = store.store_id
                    updated = True
            if updated:
                session.commit()

    def _ensure_auth_records(self) -> None:
        with self._session_factory() as session:
            users = session.scalars(select(ManagedUserModel)).all()
            auth_updated = False
            data_updated = False
            for user in users:
                selected_role = self._normalized_role_for_existing_user(user)
                derived_permissions = self._permissions_for_selected_role(selected_role)
                if tuple(role.role_name for role in user.roles) != (selected_role,):
                    user.roles[:] = [ManagedUserRoleModel(user_id=user.user_id, role_name=selected_role)]
                    data_updated = True
                if tuple(sorted(permission.permission_name for permission in user.permissions)) != derived_permissions:
                    user.permissions[:] = [
                        ManagedUserPermissionModel(
                            user_id=user.user_id,
                            permission_name=permission_name,
                        )
                        for permission_name in derived_permissions
                    ]
                    data_updated = True

                if user.auth_record is None:
                    user.auth_record = ManagedUserAuthModel(
                        user_id=user.user_id,
                        mobile=self._extract_mobile(user.contact_info),
                        password_hash=self._password_hasher(
                            self.default_password_for_username(user.username)
                        ),
                        failed_attempts=0,
                        lockout_until=None,
                        password_reset_required=True,
                    )
                    auth_updated = True
                    continue

                mobile = self._extract_mobile(user.contact_info)
                if user.auth_record.mobile != mobile:
                    user.auth_record.mobile = mobile
                    auth_updated = True

            if auth_updated or data_updated:
                session.commit()

    def _backfill_staff_metadata(self) -> None:
        with self._session_factory() as session:
            stores = {
                store.store_id: store
                for store in session.scalars(select(ManagedStoreModel)).all()
            }
            users = session.scalars(select(ManagedUserModel)).all()
            updated = False
            for user in users:
                if user.speciality is None:
                    user.speciality = ""
                    updated = True
                if user.joining_date is None:
                    user.joining_date = user.created_on
                    updated = True
                if user.created_by_user_id:
                    continue
                if not user.store_id:
                    continue
                normalized_role = self._normalized_role_for_existing_user(user)
                if normalized_role not in {"Manager", "Worker"}:
                    continue
                store = stores.get(user.store_id)
                if store is None or not store.store_admin_user_id:
                    continue
                user.created_by_user_id = store.store_admin_user_id
                updated = True
            if updated:
                session.commit()

    def _build_user(
        self,
        *,
        user_id: str,
        username: str,
        full_name: str,
        contact_info: str,
        store_id: str | None,
        created_on: datetime,
        roles: list[str],
        permissions: list[str],
        activities: list[tuple[datetime, str]],
        speciality: str = "",
        joining_date: datetime | None = None,
        created_by_user_id: str | None = None,
    ) -> ManagedUserModel:
        user = ManagedUserModel(
            user_id=user_id,
            username=username,
            full_name=full_name,
            contact_info=contact_info,
            store_id=store_id,
            speciality=speciality,
            joining_date=joining_date or created_on,
            created_by_user_id=created_by_user_id,
            created_on=created_on,
        )
        user.roles = [
            ManagedUserRoleModel(user_id=user_id, role_name=role_name)
            for role_name in roles
        ]
        user.permissions = [
            ManagedUserPermissionModel(user_id=user_id, permission_name=permission_name)
            for permission_name in permissions
        ]
        user.activities = [
            ManagedUserActivityModel(
                user_id=user_id,
                occurred_at=occurred_at,
                summary=summary,
            )
            for occurred_at, summary in activities
        ]
        return user

    def _build_superadmin_user(
        self,
        *,
        user_id: str,
        created_on: datetime,
        activity_summary: str,
    ) -> ManagedUserModel:
        return self._build_user(
            user_id=user_id,
            username="superadmin",
            full_name="Superadmin User",
            contact_info="+15551230000 | superadmin@planning.local",
            store_id=None,
            created_on=created_on,
            roles=["Superadmin"],
            permissions=list(self.permissions_for_role("Superadmin")),
            activities=[(created_on, activity_summary)],
        )

    def _to_store_record(
        self,
        row: ManagedStoreModel,
        *,
        session: Session | None = None,
    ) -> AdminStoreRecord:
        store_admin = (
            session.get(ManagedUserModel, row.store_admin_user_id)
            if session is not None and row.store_admin_user_id
            else None
        )
        return AdminStoreRecord(
            store_id=row.store_id,
            store_code=row.store_code,
            store_name=row.store_name,
            address=row.address or "",
            city=row.city,
            manager_name=row.manager_name,
            contact_info=row.contact_info,
            owner_name=row.owner_name or "",
            owner_mobile=row.owner_mobile or "",
            owner_email=row.owner_email or "",
            store_admin_user_id=row.store_admin_user_id,
            store_admin_username=store_admin.username if store_admin is not None else "",
            store_admin_full_name=store_admin.full_name if store_admin is not None else "",
            store_admin_mobile=(
                self._extract_mobile(store_admin.contact_info) or ""
                if store_admin is not None
                else ""
            ),
            store_admin_email=(
                self._extract_email(store_admin.contact_info) or ""
                if store_admin is not None
                else ""
            ),
            status=row.status,
            created_on=self._ensure_utc(row.created_on),
            updated_on=self._ensure_utc(row.updated_on),
        )

    def _to_role_definition(self, row: ManagedRoleDefinitionModel) -> AdminRoleDefinition:
        return AdminRoleDefinition(
            role_name=row.role_name,
            scope=row.scope,
            description=row.description,
            permissions=self._deserialize_permissions(row.permission_blob),
            is_active=row.is_active,
            created_on=self._ensure_utc(row.created_on),
            updated_on=self._ensure_utc(row.updated_on),
        )

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _resolve_store_scope(
        self,
        *,
        actor_user_id: str | None = None,
        explicit_store_id: str | None = None,
    ) -> str | None:
        if explicit_store_id is not None:
            return explicit_store_id
        actor_role = self.role_name_for_user(actor_user_id)
        if actor_role == "Superadmin":
            return None
        return self.store_id_for_user(actor_user_id)

    def _contact_number_for_user(self, user: ManagedUserModel) -> str:
        if user.auth_record is not None and user.auth_record.mobile:
            return user.auth_record.mobile
        extracted_mobile = self._extract_mobile(user.contact_info)
        if extracted_mobile:
            return extracted_mobile
        return user.contact_info.split("|", maxsplit=1)[0].strip()

    def _creator_name_for_user(self, *, session: Session, user: ManagedUserModel) -> str:
        if not user.created_by_user_id:
            return ""
        creator = session.get(ManagedUserModel, user.created_by_user_id)
        return creator.full_name if creator is not None else ""

    def _extract_mobile(self, contact_info: str) -> str | None:
        match = re.search(r"(?:\+\d{7,15}|\d{7,15})", contact_info)
        if match is None:
            return None
        return match.group(0)

    def _extract_email(self, contact_info: str) -> str | None:
        match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", contact_info, flags=re.IGNORECASE)
        if match is None:
            return None
        return match.group(0)

    def _compose_contact_info(self, *, mobile: str, email: str) -> str:
        contact_parts = [mobile.strip(), email.strip().lower()]
        return " | ".join(part for part in contact_parts if part)

    def _normalize_managed_username(self, username: str) -> str:
        normalized_username = username.strip().lower()
        if not normalized_username:
            raise ValueError("Username is required before a new staff member can be created.")
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", normalized_username):
            raise ValueError(
                "Username can only contain letters, numbers, dots, underscores, and hyphens."
            )
        return normalized_username

    def _normalize_required_value(self, value: str, message: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError(message)
        return normalized_value

    def _normalize_joining_date(self, joining_date: datetime) -> datetime:
        if not isinstance(joining_date, datetime):
            raise ValueError("Joining date is required.")
        normalized_date = joining_date
        if normalized_date.tzinfo is None:
            normalized_date = normalized_date.replace(tzinfo=timezone.utc)
        else:
            normalized_date = normalized_date.astimezone(timezone.utc)
        return normalized_date.replace(hour=0, minute=0, second=0, microsecond=0)

    def _normalize_staff_role_for_actor(
        self,
        *,
        actor_user_id: str | None,
        role_name: str,
    ) -> str:
        selected_role = role_name.strip().title()
        allowed_roles = set(self.available_roles_for_actor(actor_user_id)) & {"Manager", "Worker"}
        if selected_role not in allowed_roles:
            allowed_label = ", ".join(sorted(allowed_roles)) or "Manager, Worker"
            raise ValueError(f"This account can only assign these staff roles: {allowed_label}.")
        return selected_role

    def _assert_staff_manageable(
        self,
        *,
        actor_user_id: str | None,
        target_user: ManagedUserModel,
        require_creator_match: bool,
    ) -> None:
        actor_role = self.role_name_for_user(actor_user_id)
        if actor_role == "Superadmin":
            return

        actor_store_id = self.store_id_for_user(actor_user_id)
        target_role = self._normalized_role_for_existing_user(target_user)
        allowed_roles = set(self.available_roles_for_actor(actor_user_id))
        if actor_store_id is None or target_user.store_id != actor_store_id:
            raise ValueError("This account cannot manage staff outside the active store.")
        if target_role not in allowed_roles:
            raise ValueError("This account cannot manage the selected user.")
        if require_creator_match and actor_user_id is not None and target_user.created_by_user_id != actor_user_id:
            raise ValueError("This account can only manage staff members it created.")

    def _normalize_store_fields(
        self,
        *,
        store_code: str,
        store_name: str,
        address: str,
        city: str,
        manager_name: str,
        contact_info: str,
        status: str,
    ) -> dict[str, str]:
        normalized_store_code = store_code.strip().upper()
        normalized_store_name = store_name.strip()
        normalized_address = address.strip()
        normalized_city = city.strip()
        normalized_manager_name = manager_name.strip()
        normalized_contact_info = contact_info.strip()
        normalized_status = self._normalize_store_status(status)
        if not normalized_store_code:
            raise ValueError("Store code is required.")
        if not normalized_store_name:
            raise ValueError("Store name is required.")
        if not normalized_address:
            raise ValueError("Store address is required.")
        if not normalized_city:
            raise ValueError("City is required.")
        if not normalized_manager_name:
            raise ValueError("Manager name is required.")
        if not normalized_contact_info:
            raise ValueError("Store contact information is required.")
        return {
            "store_code": normalized_store_code,
            "store_name": normalized_store_name,
            "address": normalized_address,
            "city": normalized_city,
            "manager_name": normalized_manager_name,
            "contact_info": normalized_contact_info,
            "status": normalized_status,
        }

    def _normalize_owner_fields(
        self,
        *,
        owner_name: str,
        owner_mobile: str,
        owner_email: str,
    ) -> dict[str, str]:
        normalized_owner_name = owner_name.strip()
        normalized_owner_mobile = owner_mobile.strip()
        normalized_owner_email = owner_email.strip().lower()
        if not normalized_owner_name:
            raise ValueError("Store owner name is required.")
        if not normalized_owner_mobile:
            raise ValueError("Store owner mobile is required.")
        if not normalized_owner_email:
            raise ValueError("Store owner email is required.")
        return {
            "owner_name": normalized_owner_name,
            "owner_mobile": normalized_owner_mobile,
            "owner_email": normalized_owner_email,
        }

    def _normalize_store_admin_fields(
        self,
        *,
        username: str,
        full_name: str,
        mobile: str,
        email: str,
        require_all_fields: bool,
    ) -> dict[str, str] | None:
        normalized_username = username.strip().lower()
        normalized_full_name = full_name.strip()
        normalized_mobile = mobile.strip()
        normalized_email = email.strip().lower()
        field_values = (
            normalized_username,
            normalized_full_name,
            normalized_mobile,
            normalized_email,
        )
        if not any(field_values):
            if require_all_fields:
                raise ValueError("Store admin user details are required.")
            return None
        if not all(field_values):
            raise ValueError(
                "Store admin username, name, mobile, and email are all required together."
            )
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", normalized_username):
            raise ValueError(
                "Store admin username can only contain letters, numbers, dots, underscores, and hyphens."
            )
        return {
            "username": normalized_username,
            "full_name": normalized_full_name,
            "mobile": normalized_mobile,
            "email": normalized_email,
        }

    def _ensure_user_schema_columns(self) -> None:
        inspector = inspect(self._engine)
        table_names = set(inspector.get_table_names())
        if "managed_users" not in table_names:
            return

        existing_columns = {
            column["name"]
            for column in inspector.get_columns("managed_users")
        }
        required_columns = {
            "store_id": "ALTER TABLE managed_users ADD COLUMN store_id VARCHAR(50)",
            "speciality": "ALTER TABLE managed_users ADD COLUMN speciality VARCHAR(150)",
            "joining_date": "ALTER TABLE managed_users ADD COLUMN joining_date DATETIME",
            "created_by_user_id": "ALTER TABLE managed_users ADD COLUMN created_by_user_id VARCHAR(50)",
        }
        missing_statements = [
            statement
            for column_name, statement in required_columns.items()
            if column_name not in existing_columns
        ]
        if not missing_statements:
            return

        with self._engine.begin() as connection:
            for statement in missing_statements:
                connection.exec_driver_sql(statement)

    def _ensure_store_schema_columns(self) -> None:
        inspector = inspect(self._engine)
        table_names = set(inspector.get_table_names())
        if "managed_stores" not in table_names:
            return

        existing_columns = {
            column["name"]
            for column in inspector.get_columns("managed_stores")
        }
        required_columns = {
            "address": "ALTER TABLE managed_stores ADD COLUMN address VARCHAR(250)",
            "owner_name": "ALTER TABLE managed_stores ADD COLUMN owner_name VARCHAR(150)",
            "owner_mobile": "ALTER TABLE managed_stores ADD COLUMN owner_mobile VARCHAR(50)",
            "owner_email": "ALTER TABLE managed_stores ADD COLUMN owner_email VARCHAR(200)",
            "store_admin_user_id": "ALTER TABLE managed_stores ADD COLUMN store_admin_user_id VARCHAR(50)",
        }
        missing_statements = [
            statement
            for column_name, statement in required_columns.items()
            if column_name not in existing_columns
        ]
        if not missing_statements:
            return

        with self._engine.begin() as connection:
            for statement in missing_statements:
                connection.exec_driver_sql(statement)

    def _ordered_role_names(self, role_names: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        present_role_names = set(role_names)
        ordered = [
            role_name
            for role_name in self.role_options()
            if role_name in present_role_names
        ]
        ordered.extend(
            role_name
            for role_name in sorted(present_role_names)
            if role_name not in ordered
        )
        return tuple(ordered)

    def _normalize_role_selection(self, roles: list[str]) -> str:
        available_roles = set(self.role_options())
        for role_name in roles:
            if role_name in available_roles:
                return role_name
        return "Worker"

    def _permissions_for_selected_role(self, role_name: str) -> list[str]:
        return list(self.permissions_for_role(role_name))

    def _normalized_role_for_existing_user(self, user: ManagedUserModel) -> str:
        role_names = {role.role_name for role in user.roles}
        permission_names = {permission.permission_name for permission in user.permissions}

        for role_name in self.ROLE_OPTIONS:
            if role_name in role_names:
                return role_name

        if user.username == "superadmin":
            return "Superadmin"
        if user.username == "admin":
            return "Admin"
        if role_names & {"System Admin"}:
            return "Superadmin" if user.username == "admin" else "Admin"
        if role_names & {"Billing Analyst"}:
            return "Manager"
        if role_names & {"Support Agent"}:
            return "Worker"
        if role_names & {"Audit Reader", "Security Officer"}:
            return "Admin"
        if {"customer:create", "customer:update", "billing:update"} & permission_names:
            return "Manager"
        if {"order:status:inprogress", "order:status:hold", "order:status:ready"} <= permission_names:
            return "Worker"
        return "Worker"

    def _normalize_store_status(self, status: str) -> str:
        normalized_status = status.strip().title()
        if normalized_status not in self.STORE_STATUS_OPTIONS:
            raise ValueError("Store status must be Active or Inactive.")
        return normalized_status

    def _normalize_permission_values(self, permissions: list[str]) -> list[str]:
        ordered_permissions = dict.fromkeys(
            permission.strip()
            for permission in permissions
            if permission.strip()
        )
        return list(ordered_permissions)

    def _serialize_permissions(self, permissions: tuple[str, ...] | list[str]) -> str:
        return "\n".join(self._normalize_permission_values(list(permissions)))

    def _deserialize_permissions(self, permission_blob: str) -> tuple[str, ...]:
        return tuple(
            self._normalize_permission_values(
                re.split(r"[\n,;|]+", permission_blob.strip())
            )
        )

    def _role_sort_key(self, role_name: str) -> tuple[int, int, str]:
        if role_name == "Superadmin":
            return (0, 0, role_name.lower())
        if role_name == "Admin":
            return (0, 1, role_name.lower())
        if role_name == "Manager":
            return (0, 2, role_name.lower())
        if role_name == "Worker":
            return (0, 3, role_name.lower())
        return (1, 99, role_name.lower())
