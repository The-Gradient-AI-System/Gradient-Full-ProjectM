import base64
import json
import os
from pathlib import Path


def _parse_token_from_env() -> dict | None:
    raw_json = os.getenv("GMAIL_TOKEN_JSON", "").strip()
    if raw_json:
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            return None

    raw_b64 = os.getenv("GMAIL_TOKEN_JSON_B64", "").strip()
    if raw_b64:
        try:
            decoded = base64.b64decode(raw_b64).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return None

    return None


def ensure_token_file(token_file: Path) -> bool:
    """
    Ensure Google token file exists on ephemeral hosts (e.g. Render free).

    Priority:
    1) Existing token_file on disk
    2) GMAIL_TOKEN_JSON env var
    3) GMAIL_TOKEN_JSON_B64 env var
    """
    if token_file.exists():
        return True

    token_payload = _parse_token_from_env()
    if not token_payload:
        return False

    # Minimal sanity check for OAuth token payload.
    if "refresh_token" not in token_payload and "access_token" not in token_payload:
        return False

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps(token_payload, ensure_ascii=False), encoding="utf-8")
    return True
