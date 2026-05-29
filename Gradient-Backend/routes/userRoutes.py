from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Security, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from db import db_lock, get_conn
from service.leadService import get_current_user_role
from service.userService import (
    get_managers_with_online_status,
    login_user,
    mark_user_offline,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
users_router = APIRouter(prefix="/users", tags=["Users"])
security = HTTPBearer()

BASE_DIR = Path(__file__).resolve().parent.parent
AVATARS_DIR = BASE_DIR / "static" / "avatars"
AVATARS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024
CONTENT_TYPE_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}


def get_user_from_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Extract user info from Authorization header"""
    token = credentials.credentials
    return get_current_user_role(token)


def get_user_from_token_no_activity(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    return get_current_user_role(token, update_activity=False)


class User(BaseModel):
    username: str
    email: EmailStr
    password: str


@router.post("/register")
def register(user: User, user_info: dict = Depends(get_user_from_token)):
    if user_info.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can register new users")
    return register_user(user)


@router.post("/login")
def login(user: User):
    return login_user(user)


@router.post("/logout")
def logout(user_info: dict = Depends(get_user_from_token_no_activity)):
    if user_info.get("role") == "manager":
        mark_user_offline(user_info["id"])
    return {"msg": "Logged out successfully"}


@users_router.get("/managers/status")
def get_managers_status(_: dict = Depends(get_user_from_token)):
    return {"managers": get_managers_with_online_status()}


def _resolve_avatar_extension(file: UploadFile) -> str:
    filename_ext = Path(file.filename or "").suffix.lower()
    if filename_ext in ALLOWED_AVATAR_EXTENSIONS:
        return filename_ext
    content_type = (file.content_type or "").lower()
    return CONTENT_TYPE_TO_EXT.get(content_type, "")


def _delete_avatar_file(avatar_url: str | None) -> None:
    if not avatar_url or not avatar_url.startswith("/static/avatars/"):
        return
    path = BASE_DIR / avatar_url.lstrip("/")
    if path.is_file():
        path.unlink(missing_ok=True)


@users_router.post("/avatar")
async def upload_user_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_user_from_token),
):
    extension = _resolve_avatar_extension(file)
    if not extension:
        raise HTTPException(
            status_code=400,
            detail="Дозволені формати: PNG, JPG, JPEG",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Файл порожній")
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Файл завеликий (макс. 5 МБ)")

    user_id = current_user["id"]
    filename = f"avatar_{user_id}{extension}"
    avatar_url = f"/static/avatars/{filename}"
    target_path = AVATARS_DIR / filename

    with db_lock:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT avatar_url FROM users WHERE id = ?",
                [user_id],
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            previous_avatar = row[0]

        target_path.write_bytes(content)

        with get_conn() as conn:
            conn.execute(
                "UPDATE users SET avatar_url = ? WHERE id = ?",
                [avatar_url, user_id],
            )
            conn.commit()

    if previous_avatar and previous_avatar != avatar_url:
        _delete_avatar_file(previous_avatar)

    return {"avatar_url": avatar_url}
