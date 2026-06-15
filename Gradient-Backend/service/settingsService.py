import os
import time
from typing import Dict

from db import get_conn, db_lock, upsert_app_setting

ReplyPrompts = Dict[str, str]

FOLLOW_UP_KEY = "reply_prompt_follow_up"
RECAP_KEY = "reply_prompt_recap"
QUICK_KEY = "reply_prompt_quick"
TOP_BLOCK_KEY = "reply_top_block"
BOTTOM_BLOCK_KEY = "reply_bottom_block"
STYLE_OFFICIAL_KEY = "reply_style_official"
STYLE_SEMI_OFFICIAL_KEY = "reply_style_semi_official"

_REPLY_SETTINGS_KEYS = (
    FOLLOW_UP_KEY,
    RECAP_KEY,
    QUICK_KEY,
    TOP_BLOCK_KEY,
    BOTTOM_BLOCK_KEY,
    STYLE_OFFICIAL_KEY,
    STYLE_SEMI_OFFICIAL_KEY,
)

try:
    _REPLY_SETTINGS_CACHE_SECONDS = max(
        0, int(os.getenv("REPLY_SETTINGS_CACHE_SECONDS", "120"))
    )
except ValueError:
    _REPLY_SETTINGS_CACHE_SECONDS = 120

_reply_settings_cache: dict[str, object] | None = None
_reply_settings_cached_at: float = 0.0


def invalidate_reply_settings_cache() -> None:
    global _reply_settings_cache, _reply_settings_cached_at
    _reply_settings_cache = None
    _reply_settings_cached_at = 0.0


def get_setting(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", [key]).fetchone()
    return row[0] if row else None


def set_setting(key: str, value: str) -> None:
    with db_lock:
        with get_conn() as conn:
            upsert_app_setting(conn, key, value)
            conn.commit()


def get_reply_prompts() -> ReplyPrompts:
    return {
        "follow_up": get_setting(FOLLOW_UP_KEY) or "",
        "recap": get_setting(RECAP_KEY) or "",
        "quick": get_setting(QUICK_KEY) or "",
    }


def update_reply_prompts(follow_up: str, recap: str, quick: str) -> ReplyPrompts:
    set_setting(FOLLOW_UP_KEY, follow_up)
    set_setting(RECAP_KEY, recap)
    set_setting(QUICK_KEY, quick)
    invalidate_reply_settings_cache()
    return get_reply_prompts()


def get_reply_blocks() -> dict[str, str]:
    return {
        "topBlock": get_setting(TOP_BLOCK_KEY) or "",
        "bottomBlock": get_setting(BOTTOM_BLOCK_KEY) or "",
    }


def update_reply_blocks(top_block: str, bottom_block: str) -> dict[str, str]:
    set_setting(TOP_BLOCK_KEY, top_block)
    set_setting(BOTTOM_BLOCK_KEY, bottom_block)
    invalidate_reply_settings_cache()
    return get_reply_blocks()


def get_reply_settings() -> dict[str, object]:
    global _reply_settings_cache, _reply_settings_cached_at

    now = time.time()
    if (
        _REPLY_SETTINGS_CACHE_SECONDS > 0
        and _reply_settings_cache is not None
        and (now - _reply_settings_cached_at) < _REPLY_SETTINGS_CACHE_SECONDS
    ):
        return _reply_settings_cache

    placeholders = ", ".join(["?"] * len(_REPLY_SETTINGS_KEYS))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT key, value FROM app_settings WHERE key IN ({placeholders})",
            list(_REPLY_SETTINGS_KEYS),
        ).fetchall()

    values = {row[0]: (row[1] or "") for row in rows}
    settings: dict[str, object] = {
        "topBlock": values.get(TOP_BLOCK_KEY, ""),
        "bottomBlock": values.get(BOTTOM_BLOCK_KEY, ""),
        "styles": {
            "official": values.get(STYLE_OFFICIAL_KEY, ""),
            "semi_official": values.get(STYLE_SEMI_OFFICIAL_KEY, ""),
        },
        "prompts": {
            "follow_up": values.get(FOLLOW_UP_KEY, ""),
            "recap": values.get(RECAP_KEY, ""),
            "quick": values.get(QUICK_KEY, ""),
        },
    }

    if _REPLY_SETTINGS_CACHE_SECONDS > 0:
        _reply_settings_cache = settings
        _reply_settings_cached_at = now

    return settings


def update_reply_settings(
    *,
    top_block: str,
    bottom_block: str,
    style_official: str,
    style_semi_official: str,
    follow_up: str,
    recap: str,
    quick: str,
) -> dict[str, object]:
    update_reply_blocks(top_block, bottom_block)
    set_setting(STYLE_OFFICIAL_KEY, style_official)
    set_setting(STYLE_SEMI_OFFICIAL_KEY, style_semi_official)
    update_reply_prompts(follow_up, recap, quick)
    invalidate_reply_settings_cache()
    return get_reply_settings()
