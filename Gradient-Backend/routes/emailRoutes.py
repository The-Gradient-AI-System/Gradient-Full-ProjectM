from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Literal
import base64
import mimetypes

from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

from pydantic import BaseModel

from service.gmailService import get_gmail_service
from service.leadService import get_current_user_role
from db import get_conn, db_lock

router = APIRouter(prefix="/email", tags=["Email"])
emails_router = APIRouter(prefix="/emails", tags=["Emails"])
security = HTTPBearer()

def get_user_from_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Extract user info from Authorization header"""
    token = credentials.credentials
    return get_current_user_role(token)


def current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """Authorized user with id and username."""
    return get_current_user_role(credentials.credentials)


_EMAIL_SELECT = """
    SELECT
        gmail_id, status, first_name, last_name, full_name, email, subject,
        received_at, company, body, phone, website, company_name, company_info,
        person_role, person_links, person_location, person_experience, person_summary,
        person_insights, company_insights, assigned_to, assigned_manager_id,
        assigned_at, last_action_by, synced_at, created_at
    FROM gmail_messages
    WHERE gmail_id = ?
"""


def _format_email_row(row: tuple) -> dict:
    return {
        "gmail_id": row[0],
        "status": row[1] or "новий",
        "first_name": row[2] or "",
        "last_name": row[3] or "",
        "full_name": row[4] or "",
        "email": row[5] or "",
        "subject": row[6] or "",
        "received_at": row[7] or "",
        "company": row[8] or "",
        "body": row[9] or "",
        "phone": row[10] or "",
        "website": row[11] or "",
        "company_name": row[12] or "",
        "company_info": row[13] or "",
        "person_role": row[14] or "",
        "person_links": row[15] or "",
        "person_location": row[16] or "",
        "person_experience": row[17] or "",
        "person_summary": row[18] or "",
        "person_insights": row[19] or "",
        "company_insights": row[20] or [],
        "assigned_to": row[21],
        "assigned_manager_id": row[22],
        "assigned_at": row[23],
        "last_action_by": row[24],
        "synced_at": row[25],
        "created_at": row[26],
    }


class EmailActionRequest(BaseModel):
    action: Literal["confirm", "postpone", "take_to_work", "reject", "restore"]


@emails_router.post("/{msg_id}/action")
def apply_email_action(
    msg_id: str,
    payload: EmailActionRequest,
    user: dict = Depends(current_user),
):
    user_id = user["id"]
    username = user["username"]
    action = payload.action

    with db_lock:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT gmail_id, status, assigned_manager_id FROM gmail_messages WHERE gmail_id = ?",
                [msg_id],
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Лист не знайдено")

            assigned_manager_id = row[2]

            if action == "take_to_work":
                if assigned_manager_id is not None and assigned_manager_id != user_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Лист уже в роботі у іншого менеджера",
                    )
                conn.execute(
                    """
                    UPDATE gmail_messages
                    SET status = 'в роботі',
                        assigned_manager_id = ?,
                        last_action_by = ?
                    WHERE gmail_id = ?
                    """,
                    [user_id, username, msg_id],
                )
            elif action == "confirm":
                conn.execute(
                    """
                    UPDATE gmail_messages
                    SET status = 'підтверджено',
                        assigned_manager_id = NULL,
                        last_action_by = ?
                    WHERE gmail_id = ?
                    """,
                    [username, msg_id],
                )
            elif action == "postpone":
                conn.execute(
                    """
                    UPDATE gmail_messages
                    SET status = 'відкладено',
                        last_action_by = ?
                    WHERE gmail_id = ?
                    """,
                    [username, msg_id],
                )
            elif action == "reject":
                conn.execute(
                    """
                    UPDATE gmail_messages
                    SET status = 'відхилено',
                        assigned_manager_id = NULL,
                        last_action_by = ?
                    WHERE gmail_id = ?
                    """,
                    [username, msg_id],
                )
            elif action == "restore":
                conn.execute(
                    """
                    UPDATE gmail_messages
                    SET status = 'відновлено',
                        assigned_manager_id = NULL,
                        last_action_by = ?
                    WHERE gmail_id = ?
                    """,
                    [username, msg_id],
                )

            updated = conn.execute(_EMAIL_SELECT, [msg_id]).fetchone()
            conn.commit()

    return _format_email_row(updated)

@router.post("/send")
async def send_email_with_attachments(
    to: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    attachments: List[UploadFile] = File(default=[]),
    user_info: dict = Depends(get_user_from_token)
):
    """
    Send email with attachments via Gmail API
    """
    try:
        # Build a proper multipart MIME message so Gmail can deliver attachments.
        message = MIMEMultipart()
        message["to"] = to
        message["subject"] = subject
        message.attach(MIMEText(body or "", "plain", "utf-8"))

        saved_files: List[str] = []
        for upload in attachments or []:
            if not upload:
                continue
            filename = upload.filename or "attachment"
            saved_files.append(filename)

            data = await upload.read()
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            maintype, subtype = mime_type.split("/", 1)

            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            message.attach(part)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        service = get_gmail_service()
        result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )

        # Persist outgoing reply snippet for Leads History (best-effort).
        try:
            with db_lock:
                with get_conn() as conn:
                    row = conn.execute(
                        "SELECT gmail_id FROM gmail_messages WHERE email = ? ORDER BY created_at DESC LIMIT 1",
                        [to],
                    ).fetchone()
                    if row:
                        conn.execute(
                            """
                            UPDATE gmail_messages
                            SET last_reply_subject = ?, last_reply_body = ?, last_replied_at = CURRENT_TIMESTAMP
                            WHERE gmail_id = ?
                            """,
                            [subject, body, row[0]],
                        )
                        conn.commit()
        except Exception:
            pass

        return JSONResponse(
            {
                "success": True,
                "message": f"Email sent to {to}",
                "attachments_count": len(saved_files),
                "attachments": saved_files,
                "gmail_result": result,
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
