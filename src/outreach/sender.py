"""Brevo SMTP Email Dispatcher and Outreach Campaign Sender."""

import logging
import os
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import parseaddr, formataddr
from typing import Dict, List, Optional

from src.config import (
    BREVO_SMTP_HOST,
    BREVO_SMTP_PORT,
    BREVO_SMTP_LOGIN,
    BREVO_SMTP_KEY,
    EMAIL_FROM,
    SENDER_NAME,
    SENDER_EMAIL,
    ADMIN_EMAIL
)
from src.outreach.repository import (
    get_draft_by_id,
    get_all_drafts,
    update_draft_status,
    slugify
)
from src.storage.db import get_db, DEFAULT_DB_PATH
from src.storage.sync_prospects import export_prospects_to_csv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("email_sender")

SENT_ARCHIVE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "outreach",
    "sent"
)


class EmailSenderError(Exception):
    """Custom exception for outreach email sending failures."""
    pass


def test_smtp_connection() -> bool:
    """Verify Brevo SMTP server connectivity and authentication."""
    if not BREVO_SMTP_LOGIN or not BREVO_SMTP_KEY:
        raise EmailSenderError("BREVO_SMTP_LOGIN and BREVO_SMTP_KEY must be set in .env")

    try:
        server = smtplib.SMTP(BREVO_SMTP_HOST, BREVO_SMTP_PORT, timeout=12)
        server.starttls()
        server.login(BREVO_SMTP_LOGIN, BREVO_SMTP_KEY)
        server.quit()
        return True
    except Exception as e:
        raise EmailSenderError(f"SMTP connection test failed: {e}")


def send_email_message(
    to_email: str,
    subject: str,
    body_text: str,
    to_name: Optional[str] = None
) -> None:
    """Send a single plaintext email message via Brevo SMTP."""
    if not BREVO_SMTP_LOGIN or not BREVO_SMTP_KEY:
        raise EmailSenderError("Missing Brevo credentials in .env")

    # Clean sender address and name
    name, raw_from_addr = parseaddr(EMAIL_FROM or SENDER_EMAIL or "")
    from_addr = raw_from_addr or EMAIL_FROM or SENDER_EMAIL
    from_name = SENDER_NAME or name

    # Clean recipient address and name
    r_name, raw_to_addr = parseaddr(to_email)
    target_addr = raw_to_addr or to_email
    target_name = to_name or r_name

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_addr)) if from_name else from_addr
    msg["To"] = formataddr((target_name, target_addr)) if target_name else target_addr
    msg["Reply-To"] = SENDER_EMAIL or from_addr

    msg.set_content(body_text.strip())

    try:
        server = smtplib.SMTP(BREVO_SMTP_HOST, BREVO_SMTP_PORT, timeout=15)
        server.starttls()
        server.login(BREVO_SMTP_LOGIN, BREVO_SMTP_KEY)
        server.send_message(msg, from_addr=from_addr, to_addrs=[target_addr])
        server.quit()
    except Exception as e:
        raise EmailSenderError(f"Failed to dispatch email to {target_addr}: {e}")


def archive_sent_draft(draft: Dict, sent_timestamp: str) -> str:
    """Save an archived markdown snapshot of the sent email in outreach/sent/YYYY-MM/."""
    month_folder = datetime.now().strftime("%Y-%m")
    dest_dir = os.path.join(SENT_ARCHIVE_DIR, month_folder)
    os.makedirs(dest_dir, exist_ok=True)

    slug = slugify(draft["channel_title"])
    archive_path = os.path.join(dest_dir, f"{slug}.md")

    content = f"""---
draft_id: {draft['id']}
prospect_id: "{draft['prospect_id']}"
channel_title: "{draft['channel_title']}"
recipient_email: "{draft['recipient_email']}"
status: "sent"
sent_at: "{sent_timestamp}"
subject_line: "{draft['subject_line']}"
notes: "{draft.get('notes') or ''}"
---

### Subject:
{draft['subject_line']}

### Body:
{draft['body_markdown']}
"""

    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(content)

    return archive_path


def send_admin_notification(subject: str, body_text: str) -> bool:
    """Send an administrative report/notification email to ADMIN_EMAIL."""
    if not ADMIN_EMAIL:
        logger.info("ADMIN_EMAIL not set, skipping admin notification.")
        return False
    try:
        send_email_message(
            to_email=ADMIN_EMAIL,
            subject=subject,
            body_text=body_text,
            to_name="KlipHowl Admin"
        )
        logger.info(f"✓ Notification dispatched to ADMIN_EMAIL ({ADMIN_EMAIL})")
        return True
    except Exception as e:
        logger.error(f"Failed to send admin notification to {ADMIN_EMAIL}: {e}")
        return False


def send_test_draft_to_admin(draft: Dict) -> bool:
    """Send a preview copy of an email draft directly to ADMIN_EMAIL without modifying DB status."""
    if not ADMIN_EMAIL:
        raise EmailSenderError("ADMIN_EMAIL is not configured in .env. Please add ADMIN_EMAIL=your_email@domain.com")

    subject = f"[TEST PREVIEW] {draft['subject_line']}"
    header_block = f"""======================================================================
[TEST DRAFT PREVIEW — DISPATCHED TO ADMIN: {ADMIN_EMAIL}]
Target Creator   : {draft['channel_title']}
Recipient Address: {draft['recipient_email']}
Current Status   : {draft['status']}
Draft File       : {draft.get('draft_file_path') or 'N/A'}
======================================================================

"""
    body_text = header_block + draft["body_markdown"].strip()
    send_email_message(
        to_email=ADMIN_EMAIL,
        subject=subject,
        body_text=body_text,
        to_name="KlipHowl Admin"
    )
    return True


def dispatch_draft(
    draft_id: int,
    dry_run: bool = False,
    db_path: str = DEFAULT_DB_PATH
) -> Dict:
    """Send an approved draft and update SQLite records."""
    draft = get_draft_by_id(draft_id, db_path=db_path)
    if not draft:
        raise EmailSenderError(f"Draft ID {draft_id} not found.")

    # STRICT SAFETY CHECK
    if draft["status"] != "approved":
        raise EmailSenderError(
            f"SAFETY LOCK: Draft #{draft_id} for '{draft['channel_title']}' has status '{draft['status']}'. "
            "Only drafts with status 'approved' can be sent. "
            f"Run 'uv run marketing review --approve {draft_id}' first."
        )

    recipient = draft["recipient_email"]
    subject = draft["subject_line"]
    body = draft["body_markdown"]
    title = draft["channel_title"]

    if dry_run:
        logger.info(f"[DRY RUN] Would send email #{draft_id} to {title} <{recipient}>: '{subject}'")
        return {"draft_id": draft_id, "sent": False, "dry_run": True, "recipient": recipient}

    # Dispatch email via Brevo
    send_email_message(to_email=recipient, subject=subject, body_text=body, to_name=title)
    sent_timestamp = datetime.now().isoformat()

    # Update database records
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("""
        UPDATE outreach_emails SET
            status = 'sent',
            sent_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (draft_id,))

    cur.execute("""
        UPDATE prospects SET
            outreached = 1,
            outreach_date = CURRENT_TIMESTAMP,
            status = 'in_outreach',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (draft["prospect_id"],))

    cur.execute("""
        INSERT INTO interaction_logs (outreach_email_id, event_type, details)
        VALUES (?, 'email_sent', ?)
    """, (draft_id, f"Dispatched via Brevo SMTP to {recipient}"))

    conn.commit()
    conn.close()

    # Archive copy to outreach/sent/
    archive_path = archive_sent_draft(draft, sent_timestamp)
    export_prospects_to_csv("data/exports/prospects.csv", db_path)

    logger.info(f"✓ Dispatched email #{draft_id} to {title} <{recipient}> (Archived at: {archive_path})")
    return {"draft_id": draft_id, "sent": True, "recipient": recipient, "archive_path": archive_path}


def dispatch_all_approved(
    limit: int = 20,
    delay_seconds: float = 3.0,
    dry_run: bool = False,
    db_path: str = DEFAULT_DB_PATH
) -> Dict:
    """Batch send all drafts in 'approved' status with safety pacing."""
    approved_drafts = get_all_drafts(db_path=db_path, status="approved")
    if not approved_drafts:
        return {"total_approved": 0, "sent_count": 0, "results": [], "dry_run": dry_run}

    to_process = approved_drafts[:limit]
    results = []

    for idx, d in enumerate(to_process):
        try:
            res = dispatch_draft(d["id"], dry_run=dry_run, db_path=db_path)
            results.append(res)
            # Pacing delay between sends
            if not dry_run and idx < len(to_process) - 1:
                time.sleep(delay_seconds)
        except Exception as e:
            logger.error(f"Failed to send draft #{d['id']}: {e}")
            results.append({"draft_id": d["id"], "sent": False, "error": str(e)})

    sent_count = sum(1 for r in results if r.get("sent"))
    failed_count = sum(1 for r in results if not r.get("sent") and not r.get("dry_run"))

    # Send batch dispatch summary report to ADMIN_EMAIL
    if not dry_run and ADMIN_EMAIL and results:
        lines = []
        for r in results:
            if r.get("sent"):
                lines.append(f"• [SENT] Draft #{r['draft_id']} to {r.get('recipient')}")
            else:
                lines.append(f"• [FAILED] Draft #{r['draft_id']}: {r.get('error')}")

        details_str = "\n".join(lines)
        report_subject = f"[KlipHowl Outreach] Batch Dispatch Report: {sent_count} sent, {failed_count} failed"
        report_body = f"""Hi {SENDER_NAME or 'Admin'},

Here is the confirmation summary for your outreach batch:

• Total Processed: {len(results)}
• Successfully Sent: {sent_count}
• Failed: {failed_count}
• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Delivery Log:
{details_str}

All sent drafts have been archived in outreach/sent/ and recorded in SQLite database.

Best,
KlipHowl Outreach Engine
"""
        send_admin_notification(report_subject, report_body)

    return {
        "total_approved": len(approved_drafts),
        "sent_count": sent_count,
        "results": results,
        "dry_run": dry_run
    }
