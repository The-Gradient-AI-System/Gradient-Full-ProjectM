import os
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from db import get_conn, db_lock
from service.token_store import ensure_token_file

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

# Unified scopes for the entire application (Gmail + Sheets)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _get_sheet_service():
    if not ensure_token_file(TOKEN_FILE):
        raise FileNotFoundError(
            f"token.json not found at {TOKEN_FILE}. "
            "Provide GMAIL_TOKEN_JSON (or GMAIL_TOKEN_JSON_B64) in environment "
            "or run auth_init.py first."
        )

    creds = Credentials.from_authorized_user_file(
        TOKEN_FILE,
        SCOPES
    )

    return build("sheets", "v4", credentials=creds)


def append_to_sheet(rows: list[list[str]]):
    if not rows:
        return

    service = _get_sheet_service()

    body = {"values": rows}

    service.spreadsheets().values().append(
        spreadsheetId=os.getenv("SPREADSHEET_ID"),
        range="A:T",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()


DEFAULT_HEADERS = [
    "status",
    "first_name",
    "last_name",
    "full_name",
    "email",
    "subject",
    "received_at",
    "company",
    "body",
    "phone",
    "website",
    "company_name",
    "company_info",
    "person_role",
    "person_links",
    "person_location",
    "person_experience",
    "person_summary",
    "person_insights",
    "company_insights",
]


MONTH_LABELS = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]

WEEK_LABELS = ["W1", "W2", "W3", "W4"]

DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y",
]


def fetch_sheet_rows(limit: int | None = 120) -> list[dict[str, str]]:
    service = _get_sheet_service()

    result = service.spreadsheets().values().get(
        spreadsheetId=os.getenv("SPREADSHEET_ID"),
        range="A:T"
    ).execute()

    values = result.get("values", [])
    if not values:
        return []

    header_row = values[0]
    normalized = [cell.strip().lower() for cell in header_row]

    treated_as_header = any(col in ("email", "subject", "company") for col in normalized)

    if treated_as_header:
        header = [DEFAULT_HEADERS[i] if i < len(DEFAULT_HEADERS) else f"field_{i}" for i, _ in enumerate(header_row)]
        data_rows = values[1:]
        header_offset = 1
    else:
        header = DEFAULT_HEADERS
        data_rows = values
        header_offset = 0

    data_rows = list(data_rows)
    total_rows = len(data_rows)

    if limit is not None and limit > 0:
        data_rows = data_rows[-limit:]

    trimmed_count = total_rows - len(data_rows)
    start_row_number = 1 + header_offset + trimmed_count

    indexed_rows = list(enumerate(data_rows, start=start_row_number))

    leads = []
    for row_number, row in reversed(indexed_rows):  # newest first
        entry = {}
        for idx, key in enumerate(header):
            if idx < len(DEFAULT_HEADERS):
                key = DEFAULT_HEADERS[idx]
            entry[key] = row[idx] if idx < len(row) else ""

        # Post-process JSON encoded fields
        person_links_raw = entry.get("person_links")
        if person_links_raw:
            try:
                entry["person_links"] = json.loads(person_links_raw)
            except json.JSONDecodeError:
                entry["person_links"] = [item.strip() for item in person_links_raw.split(";") if item.strip()]
        else:
            entry["person_links"] = []

        for complex_key in ("person_insights", "company_insights"):
            raw_value = entry.get(complex_key)
            if raw_value:
                try:
                    entry[complex_key] = json.loads(raw_value)
                except json.JSONDecodeError:
                    entry[complex_key] = []
            else:
                entry[complex_key] = []

        # Normalize optional fields
        entry["status"] = entry.get("status") or "waiting"
        entry["person_summary"] = entry.get("person_summary") or ""
        entry["first_name"] = entry.get("first_name") or ""
        entry["last_name"] = entry.get("last_name") or ""
        entry["sheet_row"] = row_number

        leads.append(entry)

    return leads


ALLOWED_STATUS_VALUES = {"confirmed", "rejected", "snoozed", "waiting", "new", "postponed", "in_work"}


def update_lead_status(row_number: int, status: str, rejection_reason: str | None = None) -> None:
    if row_number is None or row_number < 1:
        raise ValueError("row_number must be a positive integer")

    normalized_status = (status or "").strip().lower()
    if normalized_status not in ALLOWED_STATUS_VALUES:
        raise ValueError("Unsupported status value")

    service = _get_sheet_service()

    body = {"values": [[normalized_status]]}

    service.spreadsheets().values().update(
        spreadsheetId=os.getenv("SPREADSHEET_ID"),
        range=f"A{row_number}",
        valueInputOption="RAW",
        body=body,
    ).execute()


def update_lead_status_gmail_id(gmail_id: str, status: str, user_info: dict = None, rejection_reason: str | None = None) -> None:
    """Update lead status in DuckDB by gmail_id"""
    if not gmail_id:
        raise ValueError("gmail_id is required")

    normalized_status = (status or "").strip().lower()
    if normalized_status not in ALLOWED_STATUS_VALUES:
        raise ValueError(f"Unsupported status value: {normalized_status}")

    with db_lock:
        with get_conn() as conn:
            if normalized_status == "postponed":
                conn.execute(
                    "UPDATE gmail_messages SET status = ?, assigned_to = NULL, assigned_at = NULL WHERE gmail_id = ?",
                    [normalized_status, gmail_id],
                )
            else:
                conn.execute(
                    "UPDATE gmail_messages SET status = ? WHERE gmail_id = ?",
                    [normalized_status, gmail_id],
                )

            import uuid
            history_id = str(uuid.uuid4())

            lead_name = conn.execute(
                "SELECT full_name FROM gmail_messages WHERE gmail_id = ?",
                [gmail_id],
            ).fetchone()
            lead_name = lead_name[0] if lead_name else "Unknown"

            assignee_name = user_info.get("username") if user_info else "System"

            conn.execute(
                """
                INSERT INTO lead_status_history
                (id, gmail_id, lead_name, status, assignee, rejection_reason, changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [history_id, gmail_id, lead_name, normalized_status, assignee_name, rejection_reason, datetime.now()],
            )

            conn.commit()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(stripped, fmt)
        except ValueError:
            continue

    try:
        normalized = stripped.replace("Z", "+00:00") if stripped.endswith("Z") else stripped
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _generate_month_buckets() -> list[datetime]:
    buckets: list[datetime] = []
    current = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for _ in range(12):
        buckets.append(current)
        month = current.month - 1
        year = current.year
        if month == 0:
            month = 12
            year -= 1
        current = datetime(year, month, 1)
    return list(reversed(buckets))


def _is_qualified(lead: dict[str, str]) -> bool:
    return bool(lead.get("phone") or lead.get("website") or lead.get("company"))


def _parse_json_list(value: Any) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _attach_rejection_reasons(leads: list[dict[str, Any]]) -> None:
    """Batch-load latest rejection_reason (one query instead of N)."""
    if not leads:
        return

    gmail_ids = [lead["gmail_id"] for lead in leads if lead.get("gmail_id")]
    reason_map: dict[str, Any] = {}

    if gmail_ids:
        placeholders = ", ".join(["?"] * len(gmail_ids))
        query = f"""
            SELECT gmail_id, rejection_reason
            FROM (
                SELECT
                    gmail_id,
                    rejection_reason,
                    ROW_NUMBER() OVER (PARTITION BY gmail_id ORDER BY changed_at DESC) AS rn
                FROM lead_status_history
                WHERE gmail_id IN ({placeholders})
            ) ranked
            WHERE rn = 1
        """
        with get_conn() as conn:
            rows = conn.execute(query, gmail_ids).fetchall()
        reason_map = {row[0]: row[1] for row in rows}

    for lead in leads:
        gid = lead.get("gmail_id")
        lead["rejection_reason"] = reason_map.get(gid) if gid else None


def _lead_dict_from_row(lead: tuple) -> dict[str, Any]:
    return {
        "gmail_id": lead[0],
        "status": lead[1] or "waiting",
        "first_name": lead[2] or "",
        "last_name": lead[3] or "",
        "full_name": lead[4] or "",
        "email": lead[5] or "",
        "subject": lead[6] or "",
        "received_at": lead[7] or "",
        "company": lead[8] or "",
        "body": lead[9] or "",
        "phone": lead[10] or "",
        "website": lead[11] or "",
        "company_name": lead[12] or "",
        "company_info": lead[13] or "",
        "person_role": lead[14] or "",
        "person_links": _parse_json_list(lead[15]),
        "person_location": lead[16] or "",
        "person_experience": lead[17] or "",
        "person_summary": lead[18] or "",
        "person_insights": _parse_json_list(lead[19]),
        "company_insights": _parse_json_list(lead[20]),
        "assigned_to": lead[21],
        "assigned_at": lead[22],
        "synced_at": lead[23],
        "created_at": lead[24],
        "last_reply_subject": lead[25] or "",
        "last_reply_body": lead[26] or "",
        "last_replied_at": lead[27],
        "assigned_username": lead[28],
        "assigned_role": lead[29],
        "assigned_display": f"[{lead[29].upper()}] {lead[28]}" if lead[28] else None,
        "assigned_manager_id": lead[30],
        "last_action_by": lead[31],
    }


_ADMIN_LEADS_SELECT = """
    gmail_id, status, first_name, last_name, full_name, gm.email, subject,
    received_at, company, body, phone, website, company_name, company_info,
    person_role, person_links, person_location, person_experience, person_summary,
    person_insights, company_insights, assigned_to, assigned_at, synced_at, created_at,
    gm.last_reply_subject, gm.last_reply_body, gm.last_replied_at,
    u.username as assigned_username, u.role as assigned_role,
    gm.assigned_manager_id, gm.last_action_by
"""

_ADMIN_LEADS_SELECT_LIGHT = """
    gmail_id, status, first_name, last_name, full_name, gm.email, subject,
    received_at, company, body, phone, website, company_name, company_info,
    person_role, person_links, person_location, person_summary,
    assigned_to, assigned_at, synced_at, created_at,
    gm.last_reply_subject, gm.last_replied_at,
    u.username as assigned_username, u.role as assigned_role,
    gm.assigned_manager_id, gm.last_action_by
"""


def _lead_dict_from_row_light(lead: tuple) -> dict[str, Any]:
    body = lead[9] or ""
    if len(body) > 2000:
        body = body[:2000]

    return {
        "gmail_id": lead[0],
        "status": lead[1] or "waiting",
        "first_name": lead[2] or "",
        "last_name": lead[3] or "",
        "full_name": lead[4] or "",
        "email": lead[5] or "",
        "subject": lead[6] or "",
        "received_at": lead[7] or "",
        "company": lead[8] or "",
        "body": body,
        "phone": lead[10] or "",
        "website": lead[11] or "",
        "company_name": lead[12] or "",
        "company_info": lead[13] or "",
        "person_role": lead[14] or "",
        "person_links": _parse_json_list(lead[15]),
        "person_location": lead[16] or "",
        "person_experience": "",
        "person_summary": lead[17] or "",
        "person_insights": [],
        "company_insights": [],
        "assigned_to": lead[18],
        "assigned_at": lead[19],
        "synced_at": lead[20],
        "created_at": lead[21],
        "last_reply_subject": lead[22] or "",
        "last_reply_body": "",
        "last_replied_at": lead[23],
        "assigned_username": lead[24],
        "assigned_role": lead[25],
        "assigned_display": f"[{lead[25].upper()}] {lead[24]}" if lead[24] else None,
        "assigned_manager_id": lead[26],
        "last_action_by": lead[27],
    }


_IN_WORK_STATUS_SQL = """
    LOWER(TRIM(gm.status)) IN ('в роботі', 'in_work')
    OR UPPER(TRIM(gm.status)) = 'IN_WORK'
"""

_MY_IN_WORK_WHERE = f"""
    (gm.assigned_manager_id = ? OR gm.assigned_to = ?)
    AND ({_IN_WORK_STATUS_SQL})
"""

_VISIBLE_TO_MANAGER_WHERE = f"""
    gm.status IS NULL
    OR NOT ({_IN_WORK_STATUS_SQL})
    OR gm.assigned_manager_id = ?
    OR gm.assigned_to = ?
"""


def _count_visible_gmail_messages(user_info: dict | None) -> int:
    """Rows in gmail_messages visible to this user (no date filter, not subject to LIMIT)."""
    if not user_info:
        return 0
    role = user_info.get("role")
    if role in ("admin", "owner"):
        with get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM gmail_messages").fetchone()
        return int(row[0] if row else 0)
    if role != "manager":
        return 0
    user_id = user_info.get("id")
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) FROM gmail_messages gm WHERE {_MY_IN_WORK_WHERE}",
            [user_id, user_id],
        ).fetchone()
        in_work_count = int(row[0] if row else 0)
        if in_work_count:
            return in_work_count
        row = conn.execute(
            f"""
            SELECT COUNT(*) FROM gmail_messages gm
            WHERE {_VISIBLE_TO_MANAGER_WHERE}
            """,
            [user_id, user_id],
        ).fetchone()
    return int(row[0] if row else 0)


def build_leads_payload(limit: int | None = 120) -> dict[str, Any]:
    # Try to use database first for better performance and stability
    try:
        # Create a dummy admin user_info to reuse the robust DB logic
        dummy_admin = {"role": "admin", "id": -1}
        return build_leads_payload_from_db(limit, dummy_admin)
    except Exception as e:
        print(f"Fallback to Sheets API due to DB error: {e}")
        return build_leads_payload_from_db(limit, {"role": "admin", "id": -1})


def build_leads_payload_from_db(
    limit: int | None = 120,
    user_info: dict | None = None,
    range_days: int | None = None,
    lightweight: bool = False,
) -> dict[str, Any]:
    """Build leads payload from database with role-based filtering"""
    total_emails_all_time = _count_visible_gmail_messages(user_info)

    leads = []
    select_cols = _ADMIN_LEADS_SELECT_LIGHT if lightweight else _ADMIN_LEADS_SELECT
    row_parser = _lead_dict_from_row_light if lightweight else _lead_dict_from_row

    # Build query based on user role
    if user_info and user_info.get("role") in ("admin", "owner"):
        query = f"""
            SELECT {select_cols}
            FROM gmail_messages gm
            LEFT JOIN users u ON gm.assigned_to = u.id
            ORDER BY created_at DESC
            LIMIT ?
        """
        with get_conn() as conn:
            leads_data = conn.execute(query, [limit]).fetchall()

        leads = [row_parser(lead) for lead in leads_data]

    elif user_info and user_info.get("role") == "manager":
        # Manager logic: if manager has ANY lead with status IN_WORK, return ONLY that lead.
        # Otherwise, return all leads EXCEPT those that are IN_WORK for other managers.
        user_id = user_info.get("id")
        with db_lock:
            with get_conn() as conn:
                my_in_work = conn.execute(
                    f"SELECT 1 FROM gmail_messages gm WHERE {_MY_IN_WORK_WHERE} LIMIT 1",
                    [user_id, user_id],
                ).fetchone()

                if my_in_work:
                    query = f"""
                        SELECT {select_cols}
                        FROM gmail_messages gm
                        LEFT JOIN users u ON gm.assigned_to = u.id
                        WHERE {_MY_IN_WORK_WHERE}
                        ORDER BY created_at DESC
                    """
                    leads_data = conn.execute(query, [user_id, user_id]).fetchall()
                else:
                    query = f"""
                        SELECT {select_cols}
                        FROM gmail_messages gm
                        LEFT JOIN users u ON gm.assigned_to = u.id
                        WHERE {_VISIBLE_TO_MANAGER_WHERE}
                        ORDER BY created_at DESC
                        LIMIT ?
                    """
                    leads_data = conn.execute(query, [user_id, user_id, limit]).fetchall()

        leads = [row_parser(lead) for lead in leads_data]

    now = datetime.utcnow()

    # Optional global range filter
    if range_days is not None:
        cutoff = now - timedelta(days=range_days)
        filtered: list[dict[str, Any]] = []
        for lead in leads:
            lead_dt = _parse_datetime(lead.get("received_at"))
            if not lead_dt:
                continue
            if lead_dt >= cutoff:
                filtered.append(lead)
        leads = filtered

    _attach_rejection_reasons(leads)

    # Calculate stats
    active_cutoff = now - timedelta(days=range_days if range_days is not None else 30)

    total = len(leads)
    qualified_total = 0
    waiting_total = 0
    active_total = 0

    month_totals: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: {"total": 0, "qualified": 0})
    week_totals = [0, 0, 0, 0]
    week_qualified = [0, 0, 0, 0]

    for lead in leads:
        lead_dt = _parse_datetime(lead.get("received_at"))
        qualified = _is_qualified(lead)
        if qualified:
            qualified_total += 1

        if (lead.get("status") or "waiting").lower() == "waiting" and not qualified:
            waiting_total += 1

        if lead_dt:
            if lead_dt >= active_cutoff:
                active_total += 1

            key = (lead_dt.year, lead_dt.month)
            month_totals[key]["total"] += 1
            if qualified:
                month_totals[key]["qualified"] += 1

            diff_days = (now - lead_dt).days
            if diff_days < 0:
                diff_days = 0
            week_index = diff_days // 7
            if week_index < 4:
                slot = 3 - week_index
                week_totals[slot] += 1
                if qualified:
                    week_qualified[slot] += 1

    month_buckets = _generate_month_buckets()
    line_chart = []
    for bucket in month_buckets:
        key = (bucket.year, bucket.month)
        bucket_totals = month_totals.get(key, {"total": 0, "qualified": 0})
        line_chart.append({
            "name": MONTH_LABELS[bucket.month - 1],
            "pv": bucket_totals["total"],
            "uv": bucket_totals["qualified"],
        })

    quarter_chart = line_chart[-3:] if line_chart else []

    month_chart = [
        {"name": label, "pv": week_totals[idx], "uv": week_qualified[idx]}
        for idx, label in enumerate(WEEK_LABELS)
    ]

    percentage = 0
    if total:
        percentage = int(round((qualified_total / total) * 100))

    pie_chart = [
        {"value": percentage},
        {"value": max(0, 100 - percentage)},
    ] if total else [{"value": 0}, {"value": 100}]

    stats = {
        "active": active_total,
        "completed": total,
        "percentage": percentage,
        "qualified": qualified_total,
        "waiting": waiting_total,
        "total_emails_all_time": total_emails_all_time,
    }

    pending_groups: list[dict[str, Any]] = []
    pending_buckets: dict[str, list[dict[str, Any]]] = {"3": [], "5": [], "10": []}

    for lead in leads:
        status = (lead.get("status") or "").lower()
        if status != "waiting":
            continue
        lead_dt = _parse_datetime(lead.get("received_at"))
        if not lead_dt:
            continue
        waiting_days = (now - lead_dt).days
        if waiting_days < 3:
            continue
        if waiting_days >= 10:
            pending_buckets["10"].append(lead)
        elif waiting_days >= 5:
            pending_buckets["5"].append(lead)
        else:
            pending_buckets["3"].append(lead)

    bucket_meta = {
        "3": {"label": "3–4 дні"},
        "5": {"label": "5–9 днів"},
        "10": {"label": "10+ днів"},
    }
    for key in ["3", "5", "10"]:
        items = pending_buckets[key]
        items.sort(key=lambda x: (_parse_datetime(x.get("received_at")) or datetime.min))
        pending_groups.append(
            {
                "key": key,
                "label": bucket_meta[key]["label"],
                "count": len(items),
                "leads": items[:25],
            }
        )

    if user_info and user_info.get("role") == "manager":
        for lead in leads:
            lead["last_action_by"] = None

    return {
        "leads": leads,
        "stats": stats,
        "line": line_chart,
        "quarter": quarter_chart,
        "month": month_chart,
        "pie": pie_chart,
        "pending_groups": pending_groups,
        "generated_at": now.isoformat(),
        "user_role": user_info.get("role") if user_info else None,
        "user_id": user_info.get("id") if user_info else None
    }
