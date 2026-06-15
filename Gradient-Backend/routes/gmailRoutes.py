import logging
import os

from fastapi import APIRouter, Query, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from db import get_conn, db_lock

from service.syncService import sync_gmail_to_sheets
from service.sheetService import build_leads_payload, build_leads_payload_from_db, update_lead_status, update_lead_status_gmail_id
from service.aiService import analyze_email, generate_email_replies
from service.leadService import get_current_user_role, redact_leads_last_action_by

router = APIRouter(prefix="/gmail", tags=["Gmail"])
security = HTTPBearer()
logger = logging.getLogger(__name__)
GMAIL_DEBUG = (os.getenv("GMAIL_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"})

def get_user_from_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Extract user info from Authorization header"""
    try:
        token = credentials.credentials
        return get_current_user_role(token)
    except:
        return None

@router.post("/sync")
def manual_sync():
    count = sync_gmail_to_sheets()
    return {"saved": count}


@router.get("/leads")
def get_leads(
    limit: int | None = Query(default=120, ge=1, le=500),
    range_days: int | None = Query(default=None, ge=1, le=3650),
    lightweight: bool = Query(default=False),
    user_info: dict | None = Depends(get_user_from_token)
):
    if GMAIL_DEBUG:
        logger.debug("get_leads called, has_user=%s", bool(user_info))
    try:
        if user_info:
            # Use role-based filtering from database
            payload = build_leads_payload_from_db(
                limit, user_info, range_days=range_days, lightweight=lightweight
            )
        else:
            # Fallback to original sheet-based approach
            payload = build_leads_payload(limit)
        if user_info:
            payload["leads"] = redact_leads_last_action_by(
                payload.get("leads", []),
                user_info.get("role"),
            )
        if GMAIL_DEBUG:
            logger.debug(
                "Returning payload with %s leads, stats keys=%s",
                len(payload.get("leads", [])),
                list((payload.get("stats") or {}).keys()),
            )
        return payload
    except Exception as e:
        logger.exception("get_leads failed")
        raise HTTPException(status_code=500, detail=str(e))


class LeadInsightRequest(BaseModel):
    sender: EmailStr
    subject: str | None = ""
    body: str | None = ""


@router.post("/lead-insights")
def generate_lead_insights(payload: LeadInsightRequest):
    if not payload.body and not payload.subject:
        raise HTTPException(status_code=400, detail="Потрібно передати тему або текст листа")

    result = analyze_email(
        subject=payload.subject or "",
        body=payload.body or "",
        sender=payload.sender,
    )

    return result


class ReplyGenerationRequest(BaseModel):
    sender: EmailStr
    subject: str | None = ""
    body: str | None = ""
    lead: dict | None = None
    placeholders: dict | None = None
    prompt_overrides: dict | None = None
    style: str | None = None


@router.post("/generate-replies")
def generate_replies(payload: ReplyGenerationRequest):
    lead_data = payload.lead or {}
    email_context = {
        "sender": payload.sender,
        "subject": payload.subject or "",
        "body": payload.body or "",
    }

    replies = generate_email_replies(
        lead=lead_data,
        email=email_context,
        placeholders=payload.placeholders,
        prompt_overrides=payload.prompt_overrides,
        style=payload.style,
    )

    return {"replies": replies}


# Unified status system - supporting both old and new status values
VALID_STATUSES = {'NEW', 'ASSIGNED', 'EMAIL_SENT', 'WAITING_REPLY', 'REPLY_READY', 'CLOSED', 'LOST', 'SNOOZED', 'CONFIRMED', 'REJECTED', 'POSTPONED', 'IN_WORK'}
ALLOWED_STATUS_VALUES = {"confirmed", "rejected", "snoozed", "waiting", "new", "postponed", "in_work"}

class LeadStatusUpdateRequest(BaseModel):
    row_number: int | None = Field(gt=0, default=None)
    gmail_id: str | None = None
    status: str
    rejection_reason: str | None = None


def add_status_history(conn, gmail_id: str, status: str, assignee: str | None = None, rejection_reason: str | None = None):
    """Add entry to lead status history. Expects an already-open connection."""
    import uuid
    history_id = str(uuid.uuid4())

    lead = conn.execute(
        "SELECT full_name, email FROM gmail_messages WHERE gmail_id = ?",
        [gmail_id],
    ).fetchone()
    lead_name = lead[0] if lead else None

    conn.execute(
        """
        INSERT INTO lead_status_history (id, gmail_id, status, assignee, lead_name, rejection_reason, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [history_id, gmail_id, status, assignee, lead_name, rejection_reason, datetime.now()],
    )


@router.post("/lead-status")
def set_lead_status(payload: LeadStatusUpdateRequest, user_info: dict = Depends(get_user_from_token)):
    """Update lead status and track in history."""
    status = payload.status.upper()
    normalized_status = (payload.status or "").strip().lower()

    if status not in VALID_STATUSES and normalized_status not in ALLOWED_STATUS_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid statuses: {', '.join(VALID_STATUSES)}")

    final_status = status if status in VALID_STATUSES else normalized_status.upper()

    try:
        if payload.gmail_id:
            with db_lock:
                with get_conn() as conn:
                    lead = conn.execute(
                        "SELECT gmail_id, assigned_to, status FROM gmail_messages WHERE gmail_id = ?",
                        [payload.gmail_id],
                    ).fetchone()

                    if not lead:
                        raise HTTPException(status_code=404, detail="Lead not found")

                    lead_assigned_to = lead[1]
                    lead_status = (lead[2] or "").upper()

                    if user_info and user_info.get("role") == "manager":
                        user_id = user_info.get("id")
                        if final_status == "IN_WORK":
                            if lead_assigned_to is not None and lead_assigned_to != user_id and lead_status == "IN_WORK":
                                raise HTTPException(status_code=409, detail="Lead is already in work by another manager")
                        if final_status != "IN_WORK":
                            if lead_assigned_to is None or lead_assigned_to != user_id:
                                raise HTTPException(status_code=403, detail="You can update only leads that are in your work")

                    if final_status == "POSTPONED":
                        conn.execute(
                            "UPDATE gmail_messages SET status = 'POSTPONED', assigned_to = NULL, assigned_at = NULL WHERE gmail_id = ?",
                            [payload.gmail_id],
                        )
                    elif final_status == "IN_WORK":
                        conn.execute(
                            "UPDATE gmail_messages SET status = 'IN_WORK', assigned_to = ?, assigned_at = ? WHERE gmail_id = ?",
                            [user_info["id"], datetime.now(), payload.gmail_id],
                        )
                    else:
                        conn.execute(
                            "UPDATE gmail_messages SET status = ? WHERE gmail_id = ?",
                            [final_status, payload.gmail_id],
                        )

                    assignee = user_info.get("username") if user_info else None
                    add_status_history(conn, payload.gmail_id, final_status, assignee, payload.rejection_reason)
                    conn.commit()

                    updated_lead = conn.execute(
                        "SELECT status, assigned_to FROM gmail_messages WHERE gmail_id = ?",
                        [payload.gmail_id],
                    ).fetchone()
                    if GMAIL_DEBUG:
                        logger.debug(
                            "Lead %s updated to status=%s assigned_to=%s",
                            payload.gmail_id,
                            updated_lead[0],
                            updated_lead[1],
                        )

            return {
                "gmail_id": payload.gmail_id,
                "status": final_status,
                "updated_by": user_info.get("username") if user_info else None,
                "rejection_reason": payload.rejection_reason,
            }

        elif payload.row_number:
            update_lead_status(payload.row_number, final_status, payload.rejection_reason)
            assignee = user_info.get("username") if user_info else None
            return {
                "row_number": payload.row_number,
                "status": final_status,
                "updated_by": assignee,
                "rejection_reason": payload.rejection_reason,
            }
        else:
            raise HTTPException(status_code=400, detail="Either gmail_id or row_number must be provided")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/lead-profile")
def get_lead_profile(email: str = Query(...)):
    """Get lead profile by email with all emails from this contact"""
    with get_conn() as conn:
        emails = conn.execute(
            """
            SELECT
                gmail_id, status, first_name, last_name, full_name, email, subject,
                received_at, company, body, phone, website, company_name, company_info,
                person_role, person_links, person_location, person_experience, person_summary,
                person_insights, company_insights, assigned_to, assigned_at, created_at
            FROM gmail_messages
            WHERE email = ?
            ORDER BY created_at DESC
            """,
            [email],
        ).fetchall()

    if not emails:
        raise HTTPException(status_code=404, detail="Lead not found")

    formatted_emails = [
        {
            "gmail_id": mail[0], "status": mail[1] or "NEW",
            "first_name": mail[2] or "", "last_name": mail[3] or "",
            "full_name": mail[4] or "", "email": mail[5] or "",
            "subject": mail[6] or "", "received_at": mail[7] or "",
            "company": mail[8] or "", "body": mail[9] or "",
            "phone": mail[10] or "", "website": mail[11] or "",
            "company_name": mail[12] or "", "company_info": mail[13] or "",
            "person_role": mail[14] or "", "person_links": mail[15] or "",
            "person_location": mail[16] or "", "person_experience": mail[17] or "",
            "person_summary": mail[18] or "", "person_insights": mail[19] or [],
            "company_insights": mail[20] or [], "assigned_to": mail[21],
            "assigned_at": mail[22], "created_at": mail[23],
        }
        for mail in emails
    ]

    latest = emails[0]
    return {
        "id": latest[0], "name": latest[4] or latest[5],
        "email": latest[5], "phone": latest[10] or "",
        "company": latest[8] or latest[12] or "", "role": latest[14] or "",
        "status": latest[1] or "NEW", "pending_review": False,
        "is_priority": False, "emails": formatted_emails,
    }


@router.get("/status-history")
def get_status_history(gmail_id: str = Query(...)):
    """Get status history for a lead"""
    with get_conn() as conn:
        history = conn.execute(
            """
            SELECT id, gmail_id, changed_at, lead_name, status, assignee
            FROM lead_status_history
            WHERE gmail_id = ?
            ORDER BY changed_at DESC
            """,
            [gmail_id],
        ).fetchall()

    return {
        "history": [
            {
                "id": entry[0], "gmail_id": entry[1],
                "changed_at": entry[2], "lead_name": entry[3],
                "status": entry[4], "assignee": entry[5],
            }
            for entry in history
        ]
    }
