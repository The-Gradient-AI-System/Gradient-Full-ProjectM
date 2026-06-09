import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def avatar_path_from_url(avatar_url: str | None) -> Path | None:
    if not avatar_url:
        return None
    path_part = avatar_url.split("?", 1)[0]
    if not path_part.startswith("/static/avatars/"):
        return None
    return BASE_DIR / path_part.lstrip("/")


def delete_avatar_file(avatar_url: str | None) -> None:
    path = avatar_path_from_url(avatar_url)
    if path and path.is_file():
        path.unlink(missing_ok=True)


def build_avatar_url(filename: str) -> str:
    return f"/static/avatars/{filename}?v={int(time.time())}"


def public_avatar_url(avatar_url: str | None) -> str:
    """Return a browser-safe avatar URL or empty string if the file is missing."""
    if not avatar_url:
        return ""
    path = avatar_path_from_url(avatar_url)
    if not path or not path.is_file():
        return ""
    if "?" in avatar_url:
        return avatar_url
    stored_path = avatar_url.split("?", 1)[0]
    return f"{stored_path}?v={int(path.stat().st_mtime)}"
