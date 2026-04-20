from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class ManagedUserModel(Base):
    __tablename__ = "managed_users"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_info: Mapped[str] = mapped_column(String(200), nullable=False)
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
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    manager_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_info: Mapped[str] = mapped_column(String(200), nullable=False)
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
    created_on: datetime
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    activities: tuple[AdminUserActivity, ...]


@dataclass(frozen=True)
class AdminStoreRecord:
    store_id: str
    store_code: str
    store_name: str
    city: str
    manager_name: str
    contact_info: str
    status: str
    created_on: datetime
    updated_on: datetime


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
            "user:view",
            "user:create:admin",
            "user:create:staff",
            "user:edit",
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
        "Superadmin": "Full application control, including store and role administration.",
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
        self._seed_if_needed()
        self._ensure_default_hierarchy_users()
        self._ensure_role_definitions()
        self._ensure_store_catalog()
        self._ensure_auth_records()

    def list_users(self) -> tuple[AdminUserSummary, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ManagedUserModel).order_by(ManagedUserModel.full_name.asc())
            ).all()
            return tuple(AdminUserSummary(user_id=row.user_id, full_name=row.full_name) for row in rows)

    def list_stores(self) -> tuple[AdminStoreRecord, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ManagedStoreModel).order_by(
                    ManagedStoreModel.status.asc(),
                    ManagedStoreModel.store_name.asc(),
                )
            ).all()
            return tuple(self._to_store_record(row) for row in rows)

    def get_store(self, store_id: str) -> AdminStoreRecord | None:
        with self._session_factory() as session:
            row = session.get(ManagedStoreModel, store_id)
            if row is None:
                return None
            return self._to_store_record(row)

    def create_store(
        self,
        *,
        store_code: str,
        store_name: str,
        city: str,
        manager_name: str,
        contact_info: str,
        status: str,
    ) -> str:
        normalized_store_code = store_code.strip().upper()
        normalized_store_name = store_name.strip()
        normalized_city = city.strip()
        normalized_manager_name = manager_name.strip()
        normalized_contact_info = contact_info.strip()
        normalized_status = self._normalize_store_status(status)
        if not normalized_store_code:
            raise ValueError("Store code is required.")
        if not normalized_store_name:
            raise ValueError("Store name is required.")
        if not normalized_city:
            raise ValueError("City is required.")
        if not normalized_manager_name:
            raise ValueError("Manager name is required.")
        if not normalized_contact_info:
            raise ValueError("Contact information is required.")

        with self._session_factory() as session:
            existing_store = session.scalar(
                select(ManagedStoreModel).where(ManagedStoreModel.store_code == normalized_store_code)
            )
            if existing_store is not None:
                raise ValueError(f"Store code '{normalized_store_code}' already exists.")

            now = datetime.now(tz=timezone.utc)
            store_id = f"store-{uuid4().hex[:8]}"
            store = ManagedStoreModel(
                store_id=store_id,
                store_code=normalized_store_code,
                store_name=normalized_store_name,
                city=normalized_city,
                manager_name=normalized_manager_name,
                contact_info=normalized_contact_info,
                status=normalized_status,
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
        city: str,
        manager_name: str,
        contact_info: str,
        status: str,
    ) -> None:
        normalized_store_code = store_code.strip().upper()
        normalized_store_name = store_name.strip()
        normalized_city = city.strip()
        normalized_manager_name = manager_name.strip()
        normalized_contact_info = contact_info.strip()
        normalized_status = self._normalize_store_status(status)
        if not normalized_store_code:
            raise ValueError("Store code is required.")
        if not normalized_store_name:
            raise ValueError("Store name is required.")
        if not normalized_city:
            raise ValueError("City is required.")
        if not normalized_manager_name:
            raise ValueError("Manager name is required.")
        if not normalized_contact_info:
            raise ValueError("Contact information is required.")

        with self._session_factory() as session:
            store = session.get(ManagedStoreModel, store_id)
            if store is None:
                raise ValueError(f"Unknown store: {store_id}")

            duplicate_store = session.scalar(
                select(ManagedStoreModel).where(
                    ManagedStoreModel.store_code == normalized_store_code,
                    ManagedStoreModel.store_id != store_id,
                )
            )
            if duplicate_store is not None:
                raise ValueError(f"Store code '{normalized_store_code}' already exists.")

            store.store_code = normalized_store_code
            store.store_name = normalized_store_name
            store.city = normalized_city
            store.manager_name = normalized_manager_name
            store.contact_info = normalized_contact_info
            store.status = normalized_status
            store.updated_on = datetime.now(tz=timezone.utc)
            session.commit()

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
        return target_role in self.CREATOR_ROLE_SCOPE.get(actor_role, ())

    def default_password_for_username(self, username: str) -> str:
        normalized_username = username.strip().lower()
        return f"@ct{normalized_username}123456789"

    def get_user_profile(self, user_id: str) -> AdminUserProfile | None:
        with self._session_factory() as session:
            user = session.get(ManagedUserModel, user_id)
            if user is None:
                return None

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
        user_id: str,
        full_name: str,
        contact_info: str,
        roles: list[str],
        permissions: list[str],
    ) -> None:
        with self._session_factory() as session:
            user = session.get(ManagedUserModel, user_id)
            if user is None:
                raise ValueError(f"Unknown managed user: {user_id}")

            selected_role = self._normalize_role_selection(roles)
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
                created_on=created_on,
                roles=[self._normalize_role_selection(roles)],
                permissions=self._permissions_for_selected_role(self._normalize_role_selection(roles)),
                activities=[
                    (created_on, "User record created in admin console"),
                ],
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
            users = [
                self._build_user(
                    user_id="u-superadmin-1",
                    username="superadmin",
                    full_name="Superadmin User",
                    contact_info="+15551230000 | superadmin@planning.local",
                    created_on=now - timedelta(days=90),
                    roles=["Superadmin"],
                    permissions=list(self.permissions_for_role("Superadmin")),
                    activities=[
                        (now - timedelta(hours=2), "Created the first admin account"),
                        (now - timedelta(days=1, hours=1), "Reviewed hierarchy permissions"),
                        (now - timedelta(days=3), "Signed in from the primary workstation"),
                    ],
                ),
                self._build_user(
                    user_id="u-admin-1001",
                    username="admin",
                    full_name="General Admin",
                    contact_info="+15551230001 | admin@planning.local",
                    created_on=now - timedelta(days=60),
                    roles=["Admin"],
                    permissions=list(self.permissions_for_role("Admin")),
                    activities=[
                        (now - timedelta(hours=4), "Created a new worker account"),
                        (now - timedelta(days=2), "Updated a manager profile"),
                        (now - timedelta(days=5), "Reviewed non-superadmin users"),
                    ],
                ),
                self._build_user(
                    user_id="u-manager-1001",
                    username="manager",
                    full_name="Manager User",
                    contact_info="+15551230002 | manager@planning.local",
                    created_on=now - timedelta(days=45),
                    roles=["Manager"],
                    permissions=list(self.permissions_for_role("Manager")),
                    activities=[
                        (now - timedelta(hours=4), "Created a customer order"),
                        (now - timedelta(days=1, hours=3), "Updated customer billing receipt"),
                        (now - timedelta(days=5), "Moved an order to delivered"),
                    ],
                ),
                self._build_user(
                    user_id="u-worker-1001",
                    username="worker",
                    full_name="Worker User",
                    contact_info="+15551230003 | worker@planning.local",
                    created_on=now - timedelta(days=32),
                    roles=["Worker"],
                    permissions=list(self.permissions_for_role("Worker")),
                    activities=[
                        (now - timedelta(hours=6), "Updated an order to in progress"),
                        (now - timedelta(days=2), "Marked a ready order for dispatch"),
                        (now - timedelta(days=6), "Reviewed assigned order details"),
                    ],
                ),
            ]

            session.add_all(users)
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
                    self._build_user(
                        user_id=f"u-superadmin-{uuid4().hex[:6]}",
                        username="superadmin",
                        full_name="Superadmin User",
                        contact_info="+15551230000 | superadmin@planning.local",
                        created_on=now - timedelta(days=90),
                        roles=["Superadmin"],
                        permissions=list(self.permissions_for_role("Superadmin")),
                        activities=[(now - timedelta(days=1), "Bootstrap superadmin account created")],
                    )
                )
            if "admin" not in existing_usernames:
                bootstrap_users.append(
                    self._build_user(
                        user_id=f"u-admin-{uuid4().hex[:6]}",
                        username="admin",
                        full_name="General Admin",
                        contact_info="+15551230001 | admin@planning.local",
                        created_on=now - timedelta(days=60),
                        roles=["Admin"],
                        permissions=list(self.permissions_for_role("Admin")),
                        activities=[(now - timedelta(days=1), "Bootstrap admin account created")],
                    )
                )
            if "manager" not in existing_usernames:
                bootstrap_users.append(
                    self._build_user(
                        user_id=f"u-manager-{uuid4().hex[:6]}",
                        username="manager",
                        full_name="Manager User",
                        contact_info="+15551230002 | manager@planning.local",
                        created_on=now - timedelta(days=45),
                        roles=["Manager"],
                        permissions=list(self.permissions_for_role("Manager")),
                        activities=[(now - timedelta(days=1), "Bootstrap manager account created")],
                    )
                )
            if "worker" not in existing_usernames:
                bootstrap_users.append(
                    self._build_user(
                        user_id=f"u-worker-{uuid4().hex[:6]}",
                        username="worker",
                        full_name="Worker User",
                        contact_info="+15551230003 | worker@planning.local",
                        created_on=now - timedelta(days=30),
                        roles=["Worker"],
                        permissions=list(self.permissions_for_role("Worker")),
                        activities=[(now - timedelta(days=1), "Bootstrap worker account created")],
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

                if not row.permission_blob.strip():
                    row.permission_blob = permission_blob
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
        with self._session_factory() as session:
            store_count = session.scalar(select(func.count()).select_from(ManagedStoreModel)) or 0
            if store_count:
                return

            now = datetime.now(tz=timezone.utc)
            session.add_all(
                [
                    ManagedStoreModel(
                        store_id="store-1001",
                        store_code="ST-SEA",
                        store_name="Seattle Flagship",
                        city="Seattle",
                        manager_name="Avery Brooks",
                        contact_info="+15551001001 | seattle@planning.local",
                        status="Active",
                        created_on=now - timedelta(days=180),
                        updated_on=now - timedelta(days=2),
                    ),
                    ManagedStoreModel(
                        store_id="store-1002",
                        store_code="ST-AUS",
                        store_name="Austin Operations Hub",
                        city="Austin",
                        manager_name="Jordan Kim",
                        contact_info="+15551001002 | austin@planning.local",
                        status="Active",
                        created_on=now - timedelta(days=150),
                        updated_on=now - timedelta(days=4),
                    ),
                    ManagedStoreModel(
                        store_id="store-1003",
                        store_code="ST-DEN",
                        store_name="Denver Prep Center",
                        city="Denver",
                        manager_name="Taylor Reed",
                        contact_info="+15551001003 | denver@planning.local",
                        status="Inactive",
                        created_on=now - timedelta(days=120),
                        updated_on=now - timedelta(days=12),
                    ),
                ]
            )
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

    def _build_user(
        self,
        *,
        user_id: str,
        username: str,
        full_name: str,
        contact_info: str,
        created_on: datetime,
        roles: list[str],
        permissions: list[str],
        activities: list[tuple[datetime, str]],
    ) -> ManagedUserModel:
        user = ManagedUserModel(
            user_id=user_id,
            username=username,
            full_name=full_name,
            contact_info=contact_info,
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

    def _to_store_record(self, row: ManagedStoreModel) -> AdminStoreRecord:
        return AdminStoreRecord(
            store_id=row.store_id,
            store_code=row.store_code,
            store_name=row.store_name,
            city=row.city,
            manager_name=row.manager_name,
            contact_info=row.contact_info,
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

    def _extract_mobile(self, contact_info: str) -> str | None:
        match = re.search(r"\+\d{7,15}", contact_info)
        if match is None:
            return None
        return match.group(0)

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
