from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from db import get_conn, db_lock
from hashPswd import hash_password, verify_password
from service.leadService import get_current_user_role
from service.userService import create_access_token

router = APIRouter(prefix="/profile", tags=["Profile"])
security = HTTPBearer()


def get_user_from_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    return get_current_user_role(token)


class UpdateUsernamePayload(BaseModel):
    username: str = Field(min_length=1)


class UpdateEmailPayload(BaseModel):
    email: EmailStr


class UpdatePasswordPayload(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class UpdateProfilePayload(BaseModel):
    username: Optional[str] = Field(default=None, min_length=1)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=6)
    avatar_url: Optional[str] = None


@router.get("/me")
def get_my_profile(user_info: dict = Depends(get_user_from_token)):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, role, is_active, avatar_url FROM users WHERE id = ?",
            [user_info["id"]],
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "role": row[3],
        "is_active": bool(row[4]),
        "avatar_url": row[5] or "",
    }


@router.patch("/me/username")
def update_username(payload: UpdateUsernamePayload, user_info: dict = Depends(get_user_from_token)):
    username = payload.username.strip()

    with db_lock:
        # Step 1: read-only checks in a dedicated connection
        with get_conn() as read_conn:
            duplicate = read_conn.execute(
                "SELECT id FROM users WHERE username = ? AND id <> ?",
                [username, user_info["id"]],
            ).fetchone()
            if duplicate:
                raise HTTPException(status_code=400, detail="Це ім'я вже зайняте")

            current = read_conn.execute(
                "SELECT role FROM users WHERE id = ?",
                [user_info["id"]],
            ).fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="User not found")

            role = str(current[0]) if current[0] else "manager"

        # Step 2: write in a fresh connection (read_conn is already closed)
        with get_conn() as write_conn:
            write_conn.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                [username, user_info["id"]],
            )
            write_conn.commit()

    refreshed_token = create_access_token({"sub": username, "role": role})
    return {"username": username, "access_token": refreshed_token}


@router.patch("/me/email")
def update_email(payload: UpdateEmailPayload, user_info: dict = Depends(get_user_from_token)):
    email = str(payload.email).strip()

    with db_lock:
        # Step 1: read-only checks
        with get_conn() as read_conn:
            duplicate = read_conn.execute(
                "SELECT id FROM users WHERE email = ? AND id <> ?",
                [email, user_info["id"]],
            ).fetchone()
            if duplicate:
                raise HTTPException(status_code=400, detail="Цей email вже використовується")

            exists = read_conn.execute(
                "SELECT id FROM users WHERE id = ?",
                [user_info["id"]],
            ).fetchone()
            if not exists:
                raise HTTPException(status_code=404, detail="User not found")

        # Step 2: write
        with get_conn() as write_conn:
            write_conn.execute(
                "UPDATE users SET email = ? WHERE id = ?",
                [email, user_info["id"]],
            )
            write_conn.commit()

    return {"email": email}


@router.patch("/me/password")
def update_password(payload: UpdatePasswordPayload, user_info: dict = Depends(get_user_from_token)):
    # Step 1: read current hash (outside lock — verify_password is slow)
    with get_conn() as read_conn:
        current = read_conn.execute(
            "SELECT password FROM users WHERE id = ?",
            [user_info["id"]],
        ).fetchone()

    if not current:
        raise HTTPException(status_code=404, detail="User not found")

    stored_hash = current[0]

    if not verify_password(payload.old_password, stored_hash):
        raise HTTPException(status_code=400, detail="Старий пароль невірний")

    new_hashed = hash_password(payload.new_password)

    # Step 2: write
    with db_lock:
        with get_conn() as write_conn:
            write_conn.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                [new_hashed, user_info["id"]],
            )
            write_conn.commit()

    return {"msg": "Пароль успішно змінено"}


@router.put("/me")
def update_my_profile(payload: UpdateProfilePayload, user_info: dict = Depends(get_user_from_token)):
    """Legacy full-update endpoint kept for backwards compatibility."""
    with db_lock:
        # Step 1: read current values
        with get_conn() as read_conn:
            current = read_conn.execute(
                "SELECT username, email, role, avatar_url FROM users WHERE id = ?",
                [user_info["id"]],
            ).fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="User not found")

            username = (payload.username or current[0] or "").strip()
            email = str(payload.email or current[1] or "").strip()
            avatar_url = (payload.avatar_url if payload.avatar_url is not None else current[3] or "").strip()
            role = str(current[2]) if current[2] else "manager"

            duplicate = read_conn.execute(
                "SELECT id FROM users WHERE (username = ? OR email = ?) AND id <> ?",
                [username, email, user_info["id"]],
            ).fetchone()
            if duplicate:
                raise HTTPException(status_code=400, detail="Username or email already exists")

        # Step 2: write in a fresh connection
        with get_conn() as write_conn:
            write_conn.execute(
                "UPDATE users SET username = ?, email = ?, avatar_url = ? WHERE id = ?",
                [username, email, avatar_url, user_info["id"]],
            )
            if payload.password:
                hashed_pwd = hash_password(payload.password.strip())
                write_conn.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    [hashed_pwd, user_info["id"]],
                )
            write_conn.commit()

    refreshed_token = create_access_token({"sub": username, "role": role})
    return {
        "id": user_info["id"],
        "username": username,
        "email": email,
        "role": role,
        "avatar_url": avatar_url,
        "access_token": refreshed_token,
    }
