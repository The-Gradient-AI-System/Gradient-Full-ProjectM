"""
Password reset routes.

POST /auth/forgot-password  — request a reset code (sent to user's email)
POST /auth/reset-password   — submit code + new password to complete reset
"""

import base64
from email.mime.text import MIMEText

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from db import get_conn, db_lock
from hashPswd import hash_password
from service.passwordResetService import create_reset_code, consume_reset_code

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send_reset_email(to_email: str, code: str) -> None:
    """Send the reset code via the connected Gmail account."""
    try:
        from service.gmailService import get_gmail_service

        subject = "Код скидання пароля — Gradient"
        body = (
            f"Ваш код для скидання пароля: {code}\n\n"
            f"Код дійсний протягом 10 хвилин.\n\n"
            f"Якщо ви не запитували скидання пароля — проігноруйте цей лист."
        )

        message = MIMEText(body, "plain", "utf-8")
        message["to"] = to_email
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        service = get_gmail_service()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except Exception as exc:
        # Re-raise so the route can return a meaningful error.
        raise RuntimeError(f"Не вдалося надіслати email: {exc}") from exc


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    """Look up the user by email. If found, generate a code and send it."""
    email = str(payload.email).strip().lower()

    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ?",
            [email],
        ).fetchone()

    if not row:
        return {"msg": "Якщо такий email зареєстровано, код буде надіслано."}

    code = create_reset_code(email)

    try:
        _send_reset_email(email, code)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"msg": "Якщо такий email зареєстровано, код буде надіслано."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    """Verify the code and update the password."""
    email = str(payload.email).strip().lower()
    code = payload.code.strip()
    new_password = payload.new_password.strip()

    if not consume_reset_code(email, code):
        raise HTTPException(
            status_code=400,
            detail="Невірний або прострочений код. Спробуйте ще раз.",
        )

    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ?",
            [email],
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Користувача не знайдено.")

    user_id = row[0]
    hashed = hash_password(new_password)

    with db_lock:
        with get_conn() as conn:
            conn.execute("UPDATE users SET password = ? WHERE id = ?", [hashed, user_id])
            conn.commit()

    return {"msg": "Пароль успішно змінено. Тепер ви можете увійти."}
