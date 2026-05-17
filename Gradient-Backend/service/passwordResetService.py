"""
Password reset service.

Flow:
1. User requests reset → generate 6-digit code, store in memory with 10-min TTL, send via Gmail API.
2. User submits code + new password → verify code, update password, invalidate code.

Codes are stored in-process (dict). This is sufficient for a single-process deployment.
"""

import random
import string
from datetime import datetime, timedelta
from threading import Lock

# { email: {"code": str, "expires_at": datetime} }
_reset_store: dict[str, dict] = {}
_store_lock = Lock()

CODE_TTL_MINUTES = 10


def _generate_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def create_reset_code(email: str) -> str:
    """Generate and store a reset code for the given email. Returns the code."""
    code = _generate_code()
    expires_at = datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES)
    with _store_lock:
        _reset_store[email.lower()] = {"code": code, "expires_at": expires_at}
    return code


def verify_reset_code(email: str, code: str) -> bool:
    """Return True if the code is valid and not expired. Does NOT consume the code."""
    with _store_lock:
        entry = _reset_store.get(email.lower())
    if not entry:
        return False
    if datetime.utcnow() > entry["expires_at"]:
        # Expired — clean up
        with _store_lock:
            _reset_store.pop(email.lower(), None)
        return False
    return entry["code"] == code


def consume_reset_code(email: str, code: str) -> bool:
    """Verify and remove the code in one step. Returns True on success."""
    with _store_lock:
        entry = _reset_store.get(email.lower())
        if not entry:
            return False
        if datetime.utcnow() > entry["expires_at"]:
            _reset_store.pop(email.lower(), None)
            return False
        if entry["code"] != code:
            return False
        _reset_store.pop(email.lower(), None)
        return True
