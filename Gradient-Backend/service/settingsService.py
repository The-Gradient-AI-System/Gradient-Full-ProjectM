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
    return get_reply_prompts()


def get_reply_blocks() -> dict[str, str]:
    return {
        "topBlock": get_setting(TOP_BLOCK_KEY) or "",
        "bottomBlock": get_setting(BOTTOM_BLOCK_KEY) or "",
    }


def update_reply_blocks(top_block: str, bottom_block: str) -> dict[str, str]:
    set_setting(TOP_BLOCK_KEY, top_block)
    set_setting(BOTTOM_BLOCK_KEY, bottom_block)
    return get_reply_blocks()


def get_reply_settings() -> dict[str, object]:
    return {
        **get_reply_blocks(),
        "styles": {
            "official": get_setting(STYLE_OFFICIAL_KEY) or "",
            "semi_official": get_setting(STYLE_SEMI_OFFICIAL_KEY) or "",
        },
        "prompts": get_reply_prompts(),
    }


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
    return get_reply_settings()
