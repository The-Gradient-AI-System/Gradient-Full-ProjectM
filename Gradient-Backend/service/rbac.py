"""Role-based access helpers for owner / admin / manager."""

from __future__ import annotations

from fastapi import HTTPException

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"

STAFF_ROLES = (ROLE_OWNER, ROLE_ADMIN)
OWNER_LIST_ROLES = (ROLE_MANAGER, ROLE_ADMIN)
ADMIN_LIST_ROLES = (ROLE_MANAGER,)
OWNER_MANAGEABLE_ROLES = (ROLE_MANAGER, ROLE_ADMIN)
ADMIN_MANAGEABLE_ROLES = (ROLE_MANAGER,)

# Online status bar: managers + admins (never owner in the staff list).
STATUS_BAR_STAFF_ROLES = (ROLE_MANAGER, ROLE_ADMIN)


def is_owner(role: str | None) -> bool:
    return role == ROLE_OWNER


def is_staff(role: str | None) -> bool:
    return role in STAFF_ROLES


def list_roles_for_user(user_info: dict | None) -> tuple[str, ...]:
    """Roles visible in manager-management list."""
    if is_owner((user_info or {}).get("role")):
        return OWNER_LIST_ROLES
    return ADMIN_LIST_ROLES


def manageable_roles_for_user(user_info: dict | None) -> tuple[str, ...]:
    """Roles that may be updated/deleted via manager-management."""
    if is_owner((user_info or {}).get("role")):
        return OWNER_MANAGEABLE_ROLES
    return ADMIN_MANAGEABLE_ROLES


def status_bar_exclude_user_id(user_info: dict | None) -> int | None:
    """Who to hide from the team status bar for the current viewer.

    - owner: show all managers and admins (no exclusion).
    - admin: show all managers and other admins, but not themselves.
    """
    info = user_info or {}
    if info.get("role") == ROLE_ADMIN:
        user_id = info.get("id")
        return int(user_id) if user_id is not None else None
    return None


def assert_owner(user_info: dict | None) -> dict:
    if not user_info or not is_owner(user_info.get("role")):
        raise HTTPException(
            status_code=403,
            detail="Доступ дозволено лише власнику",
        )
    return user_info


def assert_owner_prompt_edit(user_info: dict | None) -> dict:
    """Only owner may change AI reply prompts / related settings."""
    if not user_info or not is_owner(user_info.get("role")):
        raise HTTPException(
            status_code=403,
            detail="Редагування AI промптів доступне тільки для Owner",
        )
    return user_info


def assert_owner_or_admin(user_info: dict | None) -> dict:
    """Owner and admin share access to staff-wide views (e.g. online status)."""
    role = (user_info or {}).get("role")
    if role not in (ROLE_OWNER, ROLE_ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Доступ дозволено лише власнику або адміністратору",
        )
    return user_info


def assert_staff(user_info: dict | None) -> dict:
    if not user_info or not is_staff(user_info.get("role")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_info
