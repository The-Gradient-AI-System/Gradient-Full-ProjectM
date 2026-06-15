from service.rbac import ROLE_ADMIN, ROLE_MANAGER, STATUS_BAR_STAFF_ROLES
from db import get_conn, db_lock
from hashPswd import hash_password, verify_password
from datetime import datetime, timedelta
from jose import jwt
from fastapi import HTTPException, status
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

try:
    ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "2"))
except ValueError:
    ACCESS_TOKEN_EXPIRE_HOURS = 2

try:
    ONLINE_THRESHOLD_MINUTES = int(os.getenv("ONLINE_THRESHOLD_MINUTES", "5"))
except ValueError:
    ONLINE_THRESHOLD_MINUTES = 5


def update_user_last_seen(user_id: int) -> None:
    with db_lock:
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET last_seen = ? WHERE id = ?",
                [datetime.utcnow(), user_id],
            )
            conn.commit()


def mark_user_offline(user_id: int) -> None:
    with db_lock:
        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET last_seen = NULL WHERE id = ?",
                [user_id],
            )
            conn.commit()


def _parse_last_seen(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def get_managers_with_online_status(*, exclude_user_id: int | None = None) -> list[dict]:
    threshold = datetime.utcnow() - timedelta(minutes=ONLINE_THRESHOLD_MINUTES)
    role_placeholders = ", ".join(["?"] * len(STATUS_BAR_STAFF_ROLES))

    query = f"""
            SELECT id, username, avatar_url, last_seen, role
            FROM users
            WHERE role IN ({role_placeholders})
              AND is_active IS NOT FALSE
            """
    params: list = list(STATUS_BAR_STAFF_ROLES)
    if exclude_user_id is not None:
        query += "\n              AND id != ?"
        params.append(exclude_user_id)
    query += "\n            ORDER BY role ASC, id ASC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    managers = []
    for row in rows:
        last_seen = _parse_last_seen(row[3])
        is_online = last_seen is not None and last_seen >= threshold
        managers.append(
            {
                "id": row[0],
                "username": row[1],
                "avatar_url": row[2] or "",
                "is_online": is_online,
                "role": row[4],
            }
        )
    return managers


def register_user(user):
    with db_lock:
        with get_conn() as conn:
            exists = conn.execute(
                "SELECT 1 FROM users WHERE username = ? OR email = ?",
                [user.username, user.email],
            ).fetchone()

            if exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists",
                )

            next_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM users"
            ).fetchone()[0]

            hashed_pwd = hash_password(user.password)

            conn.execute(
                "INSERT INTO users (id, username, email, password) VALUES (?, ?, ?, ?)",
                [next_id, user.username, user.email, hashed_pwd],
            )
            conn.commit()

    return {"msg": "User registered successfully"}


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def login_user(user):
    username = user.username or user.email

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, username, email, password, role, is_active, avatar_url
            FROM users
            WHERE username = ? OR email = ?
            """,
            [username, user.email or username],
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user_id, stored_username, stored_email, hashed_password, user_role, is_active, avatar_url = row

    if is_active is not None and not bool(is_active):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    if not verify_password(user.password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    role = user_role or "manager"

    if user_id and role in (ROLE_MANAGER, ROLE_ADMIN):
        update_user_last_seen(user_id)

    access_token = create_access_token({"sub": stored_username, "role": role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": role,
        "user": {
            "id": user_id,
            "username": stored_username,
            "email": stored_email or stored_username,
            "role": role,
            "avatar_url": avatar_url or "",
        },
    }
