from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PermissionEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class PermissionGrant:
    permission: str
    effect: PermissionEffect


@dataclass(frozen=True)
class RoleRecord:
    role_id: str
    name: str
    grants: tuple[PermissionGrant, ...]


@dataclass(frozen=True)
class AuthorizationContext:
    user_id: str
    roles: tuple[RoleRecord, ...]


@dataclass(frozen=True)
class EffectivePermissions:
    allowed: frozenset[str]
    denied: frozenset[str]

    def is_allowed(self, permission: str) -> bool:
        if permission in self.denied:
            return False
        return permission in self.allowed
