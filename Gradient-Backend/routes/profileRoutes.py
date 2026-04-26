from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from db import conn, db_lock
from hashPswd import hash_password
from service.leadService import get_current_user_role
from service.userService import create_access_token

router = APIRouter(prefix="/profile", tags=["Profile"])
security = HTTPBearer()


def get_user_from_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    return get_current_user_role(token)


class UpdateProfilePayload(BaseModel):
    username: str = Field(min_length=1)
    email: EmailStr
    password: str | None = Field(default=None, min_length=6)
    avatar_url: str | None = None


@router.get("/me")
def get_my_profile(user_info: dict = Depends(get_user_from_token)):
    with db_lock:
        row = conn.execute(
            """
            SELECT id, username, email, role, is_active, avatar_url
            FROM users
            WHERE id = ?
            """,
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


@router.put("/me")
def update_my_profile(payload: UpdateProfilePayload, user_info: dict = Depends(get_user_from_token)):
    username = (payload.username or "").strip()
    email = str(payload.email).strip()
    avatar_url = (payload.avatar_url or "").strip()
    password = (payload.password or "").strip()

    with db_lock:
        duplicate = conn.execute(
            """
            SELECT id
            FROM users
            WHERE (username = ? OR email = ?) AND id <> ?
            """,
            [username, email, user_info["id"]],
        ).fetchone()
    if duplicate:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    with db_lock:
        current = conn.execute(
            "SELECT role FROM users WHERE id = ?",
            [user_info["id"]],
        ).fetchone()
    if not current:
        raise HTTPException(status_code=404, detail="User not found")

    # DuckDB can throw internal vector reference errors on multi-column UPDATE in some states.
    # Apply updates in small deterministic statements to keep writes stable.
    with db_lock:
        conn.execute("UPDATE users SET username = ? WHERE id = ?", [username, user_info["id"]])
        conn.execute("UPDATE users SET email = ? WHERE id = ?", [email, user_info["id"]])
        conn.execute("UPDATE users SET avatar_url = ? WHERE id = ?", [avatar_url, user_info["id"]])
        if password:
            hashed_pwd = hash_password(password)
            conn.execute("UPDATE users SET password = ? WHERE id = ?", [hashed_pwd, user_info["id"]])
        conn.commit()

    role = current[0] or "manager"
    refreshed_token = create_access_token({"sub": username, "role": role})
    return {
        "id": user_info["id"],
        "username": username,
        "email": email,
        "role": role,
        "avatar_url": avatar_url,
        "access_token": refreshed_token,
    }
