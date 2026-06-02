from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from db import get_conn, db_lock
from hashPswd import hash_password
from service.leadService import get_current_user_role
from service.rbac import (
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_OWNER,
    assert_owner,
    assert_staff,
    list_roles_for_user,
    manageable_roles_for_user,
)

router = APIRouter(prefix="/admin/managers", tags=["Manager Management"])
security = HTTPBearer()


def get_user_from_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    return get_current_user_role(token)


def require_owner_or_admin(user_info: dict = Depends(get_user_from_token)) -> dict:
    return assert_staff(user_info)


def _roles_in_clause(roles: tuple[str, ...]) -> str:
    return ",".join(["?"] * len(roles))


class ManagerCreatePayload(BaseModel):
    username: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=6)
    avatar_url: str | None = None


class ManagerStatusPayload(BaseModel):
    is_active: bool


class ManagerResetPasswordPayload(BaseModel):
    new_password: str = Field(min_length=6)


class ManagerRolePayload(BaseModel):
    role: Literal["manager", "admin"]


@router.get("")
def list_managers(current_user: dict = Depends(require_owner_or_admin)):
    roles = list_roles_for_user(current_user)
    in_clause = _roles_in_clause(roles)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, username, email, role, is_active, avatar_url
            FROM users
            WHERE role IN ({in_clause})
            ORDER BY id ASC
            """,
            list(roles),
        ).fetchall()

    return {
        "managers": [
            {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "role": row[3],
                "is_active": bool(row[4]),
                "avatar_url": row[5] or "",
            }
            for row in rows
        ]
    }


@router.post("")
def create_manager(payload: ManagerCreatePayload, _: dict = Depends(require_owner_or_admin)):
    with db_lock:
        with get_conn() as conn:
            exists = conn.execute(
                "SELECT 1 FROM users WHERE username = ? OR email = ?",
                [payload.username, str(payload.email)],
            ).fetchone()

            if exists:
                raise HTTPException(status_code=400, detail="Username or email already exists")

            next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM users").fetchone()[0]
            hashed_pwd = hash_password(payload.password)

            conn.execute(
                "INSERT INTO users (id, username, email, password, role, is_active, avatar_url) VALUES (?, ?, ?, ?, 'manager', TRUE, ?)",
                [next_id, payload.username, str(payload.email), hashed_pwd, (payload.avatar_url or "").strip()],
            )
            conn.commit()

    return {
        "id": next_id,
        "username": payload.username,
        "email": str(payload.email),
        "role": "manager",
        "is_active": True,
        "avatar_url": (payload.avatar_url or "").strip(),
    }


def _get_manageable_user(conn, manager_id: int, current_user: dict):
    allowed_roles = manageable_roles_for_user(current_user)
    in_clause = _roles_in_clause(allowed_roles)
    row = conn.execute(
        f"SELECT id, username, role FROM users WHERE id = ? AND role IN ({in_clause})",
        [manager_id, *allowed_roles],
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Manager not found")
    return row


@router.patch("/{manager_id}/role")
def set_manager_role(
    manager_id: int,
    payload: ManagerRolePayload,
    current_user: dict = Depends(get_user_from_token),
):
    assert_owner(current_user)

    if payload.role not in (ROLE_MANAGER, ROLE_ADMIN):
        raise HTTPException(status_code=400, detail="Invalid role")

    with db_lock:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id, role FROM users WHERE id = ?",
                [manager_id],
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Manager not found")

            current_role = row[1]
            if current_role == ROLE_OWNER:
                raise HTTPException(status_code=400, detail="Cannot change owner role")

            if current_role not in (ROLE_MANAGER, ROLE_ADMIN):
                raise HTTPException(status_code=400, detail="User role cannot be changed")

            if current_role == payload.role:
                return {"id": manager_id, "role": payload.role}

            conn.execute(
                "UPDATE users SET role = ? WHERE id = ?",
                [payload.role, manager_id],
            )
            conn.commit()

    return {"id": manager_id, "role": payload.role}


@router.patch("/{manager_id}/status")
def set_manager_status(
    manager_id: int,
    payload: ManagerStatusPayload,
    current_user: dict = Depends(require_owner_or_admin),
):
    with db_lock:
        with get_conn() as conn:
            _get_manageable_user(conn, manager_id, current_user)
            conn.execute(
                "UPDATE users SET is_active = ? WHERE id = ?",
                [bool(payload.is_active), manager_id],
            )
            conn.commit()

    return {"id": manager_id, "is_active": bool(payload.is_active)}


@router.post("/{manager_id}/reset-password")
def reset_manager_password(
    manager_id: int,
    payload: ManagerResetPasswordPayload,
    current_user: dict = Depends(require_owner_or_admin),
):
    with db_lock:
        with get_conn() as conn:
            _get_manageable_user(conn, manager_id, current_user)
            hashed_pwd = hash_password(payload.new_password)
            conn.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                [hashed_pwd, manager_id],
            )
            conn.commit()

    return {"id": manager_id, "new_password": payload.new_password}


@router.delete("/{manager_id}")
def delete_manager(
    manager_id: int,
    confirm_username: str = Query(default="", description="Username confirmation (GitHub-style)"),
    current_user: dict = Depends(require_owner_or_admin),
):
    with db_lock:
        with get_conn() as conn:
            row = _get_manageable_user(conn, manager_id, current_user)
            if row[2] == ROLE_OWNER:
                raise HTTPException(status_code=400, detail="Cannot delete owner account")

            expected_username = row[1] or ""
            if (confirm_username or "").strip() != expected_username:
                raise HTTPException(status_code=400, detail="Username confirmation mismatch")

            try:
                conn.execute(
                    "UPDATE gmail_messages SET assigned_to = NULL WHERE assigned_to = ?",
                    [int(manager_id)],
                )
                conn.execute(
                    "UPDATE users SET role = 'manager_deleted', is_active = FALSE WHERE id = ?",
                    [int(manager_id)],
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise HTTPException(status_code=500, detail=f"Database error during deletion: {str(e)}")

    return {"deleted": True, "id": manager_id, "mode": "soft_delete"}
