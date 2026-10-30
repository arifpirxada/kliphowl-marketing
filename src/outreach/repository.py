"""Database repository for cold outreach candidates, email drafts, and tracking."""

import logging
import os
import re
from typing import Dict, List, Optional

from src.storage.db import get_db, DEFAULT_DB_PATH

logger = logging.getLogger("outreach_repo")

DRAFTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "outreach",
    "drafts"
)


def slugify(text: str) -> str:
    """Generate a clean slug for file naming (e.g. 'Caleb Writes Code' -> 'caleb_writes_code')."""
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text.lower()).strip('_')
    return text or "prospect"


def parse_draft_file(file_path: str) -> Optional[Dict]:
    """Parse a markdown draft file from outreach/drafts/{slug}.md into a structured dictionary."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter_data = {}
        fm_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        body_content = content
        if fm_match:
            fm_text = fm_match.group(1)
            body_content = content[fm_match.end():]
            for line in fm_text.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter_data[key.strip()] = val.strip().strip('"\'')

        # Extract Subject
        subj_match = re.search(r'###\s*Subject:\s*\n(.*?)(?=\n###\s*Body:|\Z)', body_content, re.DOTALL)
        subject = subj_match.group(1).strip() if subj_match else ""

        # Extract Body
        body_match = re.search(r'###\s*Body:\s*\n(.*)', body_content, re.DOTALL)
        body = body_match.group(1).strip() if body_match else body_content.strip()

        return {
            "prospect_id": frontmatter_data.get("prospect_id"),
            "channel_title": frontmatter_data.get("channel_title"),
            "recipient_email": frontmatter_data.get("recipient_email"),
            "status": frontmatter_data.get("status"),
            "subject": subject,
            "body": body,
            "file_path": file_path
        }
    except Exception as e:
        logger.error(f"Failed to parse draft file {file_path}: {e}")
        return None


def sync_drafts_from_disk(
    drafts_dir: str = DRAFTS_DIR,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """Scan outreach/drafts/*.md and update database if manual edits were made to markdown files."""
    if not os.path.exists(drafts_dir):
        return 0

    conn = get_db(db_path)
    cur = conn.cursor()
    updated_count = 0

    for fname in os.listdir(drafts_dir):
        if not fname.endswith(".md"):
            continue
        file_path = os.path.join(drafts_dir, fname)
        parsed = parse_draft_file(file_path)
        if not parsed:
            continue

        prospect_id = parsed.get("prospect_id")
        subject = parsed.get("subject")
        body = parsed.get("body")
        status = parsed.get("status")

        if not prospect_id or not subject or not body:
            continue

        # Look up existing draft in DB for this prospect
        cur.execute("""
            SELECT id, subject_line, body_markdown, status 
            FROM outreach_emails 
            WHERE prospect_id = ?
            ORDER BY id DESC LIMIT 1
        """, (prospect_id,))
        row = cur.fetchone()

        if row:
            # Check if file has edits compared to DB
            needs_update = (
                row["subject_line"].strip() != subject.strip() or
                row["body_markdown"].strip() != body.strip() or
                (status and status != row["status"] and row["status"] != "sent")
            )
            if needs_update:
                new_status = status if status in ("draft", "ready_for_review", "approved", "rejected") else row["status"]
                cur.execute("""
                    UPDATE outreach_emails SET
                        subject_line = ?,
                        body_markdown = ?,
                        status = ?,
                        draft_file_path = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (subject, body, new_status, file_path, row["id"]))

                cur.execute("""
                    INSERT INTO interaction_logs (outreach_email_id, event_type, details)
                    VALUES (?, 'draft_edited_from_file', 'Synced manual edits from local markdown file')
                """, (row["id"],))
                updated_count += 1

    conn.commit()
    conn.close()
    return updated_count


def get_outreach_candidates(
    db_path: str = DEFAULT_DB_PATH,
    target: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict]:
    """Retrieve prospects who have a verified primary email and are ready for outreach."""
    conn = get_db(db_path)
    cur = conn.cursor()

    query = """
        SELECT 
            p.id, p.title, p.handle, p.custom_url, p.sample_video_url,
            p.subscriber_count, p.niche_category, p.match_level,
            p.primary_email, p.email_source, p.description,
            p.outreached, p.response_status,
            v.video_id, v.title as video_title, v.view_count as video_view_count
        FROM prospects p
        LEFT JOIN (
            SELECT video_id, prospect_id, title, view_count,
                   ROW_NUMBER() OVER(PARTITION BY prospect_id ORDER BY view_count DESC) as rn
            FROM videos
        ) v ON p.id = v.prospect_id AND v.rn = 1
        WHERE p.primary_email IS NOT NULL AND p.primary_email != ''
    """
    params = []

    if target:
        query += " AND (p.id = ? OR LOWER(p.title) = LOWER(?) OR p.title LIKE ?)"
        params.extend([target, target, f"%{target}%"])

    query += " ORDER BY p.subscriber_count DESC"
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def save_email_draft(
    prospect_id: str,
    recipient_email: str,
    subject: str,
    body_markdown: str,
    referenced_video_id: Optional[str] = None,
    personalized_hook: Optional[str] = None,
    custom_instruction: Optional[str] = None,
    draft_file_path: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """Save an email draft record into the outreach_emails SQLite table."""
    conn = get_db(db_path)
    cur = conn.cursor()

    # Check if a draft already exists for this prospect
    cur.execute("""
        SELECT id FROM outreach_emails 
        WHERE prospect_id = ? AND status IN ('draft', 'ready_for_review')
    """, (prospect_id,))
    existing = cur.fetchone()

    notes = f"Generated with instruction: {custom_instruction}" if custom_instruction else None

    if existing:
        draft_id = existing["id"]
        cur.execute("""
            UPDATE outreach_emails SET
                recipient_email = ?,
                subject_line = ?,
                body_markdown = ?,
                referenced_video_id = COALESCE(?, referenced_video_id),
                personalized_hook = COALESCE(?, personalized_hook),
                status = 'ready_for_review',
                draft_file_path = COALESCE(?, draft_file_path),
                notes = COALESCE(?, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (recipient_email, subject, body_markdown, referenced_video_id, personalized_hook, draft_file_path, notes, draft_id))
    else:
        cur.execute("""
            INSERT INTO outreach_emails (
                prospect_id, recipient_email, subject_line, body_markdown,
                referenced_video_id, personalized_hook, status, draft_file_path, notes
            ) VALUES (?, ?, ?, ?, ?, ?, 'ready_for_review', ?, ?)
        """, (prospect_id, recipient_email, subject, body_markdown, referenced_video_id, personalized_hook, draft_file_path, notes))
        draft_id = cur.lastrowid

    # Log interaction
    cur.execute("""
        INSERT INTO interaction_logs (outreach_email_id, event_type, details)
        VALUES (?, 'draft_created', ?)
    """, (draft_id, notes or 'Draft created'))

    conn.commit()
    conn.close()
    return draft_id


def get_all_drafts(db_path: str = DEFAULT_DB_PATH, status: Optional[str] = None) -> List[Dict]:
    """Retrieve all email drafts from SQLite joined with prospect details."""
    sync_drafts_from_disk(db_path=db_path)
    conn = get_db(db_path)
    cur = conn.cursor()

    query = """
        SELECT 
            e.id, e.prospect_id, p.title as channel_title, e.recipient_email,
            e.subject_line, e.body_markdown, e.status, e.draft_file_path, e.notes,
            e.sent_at, e.created_at, e.updated_at
        FROM outreach_emails e
        JOIN prospects p ON e.prospect_id = p.id
    """
    params = []
    if status:
        query += " WHERE e.status = ?"
        params.append(status)

    query += " ORDER BY e.updated_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_draft_by_id(draft_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict]:
    """Retrieve a single draft by its database ID."""
    sync_drafts_from_disk(db_path=db_path)
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            e.id, e.prospect_id, p.title as channel_title, e.recipient_email,
            e.subject_line, e.body_markdown, e.status, e.draft_file_path, e.notes,
            e.sent_at, e.created_at, e.updated_at
        FROM outreach_emails e
        JOIN prospects p ON e.prospect_id = p.id
        WHERE e.id = ?
    """, (draft_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_draft_by_target(target: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict]:
    """Retrieve a single draft by prospect title or handle."""
    sync_drafts_from_disk(db_path=db_path)
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            e.id, e.prospect_id, p.title as channel_title, e.recipient_email,
            e.subject_line, e.body_markdown, e.status, e.draft_file_path, e.notes,
            e.sent_at, e.created_at, e.updated_at
        FROM outreach_emails e
        JOIN prospects p ON e.prospect_id = p.id
        WHERE p.id = ? OR LOWER(p.title) = LOWER(?) OR p.title LIKE ?
        ORDER BY e.updated_at DESC
        LIMIT 1
    """, (target, target, f"%{target}%"))
    row = cur.fetchone()
    conn.close()
    return row


def update_draft_status(
    draft_id: int,
    status: str,
    notes: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> bool:
    """Update draft status (e.g. 'approved', 'rejected', 'ready_for_review') in DB and markdown file."""
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("SELECT draft_file_path FROM outreach_emails WHERE id = ?", (draft_id,))
    row = cur.fetchone()

    cur.execute("""
        UPDATE outreach_emails 
        SET status = ?, notes = COALESCE(?, notes), updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, notes, draft_id))
    updated = cur.rowcount > 0

    if updated:
        cur.execute("""
            INSERT INTO interaction_logs (outreach_email_id, event_type, details)
            VALUES (?, ?, ?)
        """, (draft_id, f"status_{status}", notes or f"Status updated to {status}"))

        # Keep the local markdown draft file's frontmatter synchronized
        if row and row["draft_file_path"] and os.path.exists(row["draft_file_path"]):
            try:
                with open(row["draft_file_path"], "r", encoding="utf-8") as f:
                    file_content = f.read()
                new_file_content = re.sub(r'status:\s*["\']?[^"\'\n]+["\']?', f'status: "{status}"', file_content, count=1)
                with open(row["draft_file_path"], "w", encoding="utf-8") as f:
                    f.write(new_file_content)
            except Exception as e:
                logger.warning(f"Could not update status in draft file {row['draft_file_path']}: {e}")

    conn.commit()
    conn.close()
    return updated


def approve_all_ready_drafts(db_path: str = DEFAULT_DB_PATH) -> int:
    """Approve all drafts currently in 'ready_for_review' status."""
    sync_drafts_from_disk(db_path=db_path)
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id, draft_file_path FROM outreach_emails WHERE status = 'ready_for_review'")
    drafts = cur.fetchall()

    for d in drafts:
        cur.execute("""
            UPDATE outreach_emails SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (d["id"],))
        cur.execute("""
            INSERT INTO interaction_logs (outreach_email_id, event_type, details)
            VALUES (?, 'status_approved', 'Batch approved')
        """, (d["id"],))

        if d["draft_file_path"] and os.path.exists(d["draft_file_path"]):
            try:
                with open(d["draft_file_path"], "r", encoding="utf-8") as f:
                    file_content = f.read()
                new_file_content = re.sub(r'status:\s*["\']?[^"\'\n]+["\']?', 'status: "approved"', file_content, count=1)
                with open(d["draft_file_path"], "w", encoding="utf-8") as f:
                    f.write(new_file_content)
            except Exception:
                pass

    conn.commit()
    conn.close()
    return len(drafts)


def record_prospect_reply(
    target: str,
    response_status: str,
    notes: Optional[str] = None,
    signed_up: bool = False,
    free_credits: int = 0,
    db_path: str = DEFAULT_DB_PATH
) -> Optional[Dict]:
    """Record a reply or conversion from a prospect, updating prospects, outreach_emails, and interaction_logs."""
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, status FROM prospects
        WHERE id = ? OR LOWER(title) = LOWER(?) OR title LIKE ?
    """, (target, target, f"%{target}%"))
    prospect = cur.fetchone()
    if not prospect:
        conn.close()
        return None

    prospect_id = prospect["id"]
    new_prospect_status = "customer" if signed_up else ("responded" if response_status in ("interested", "not_interested") else prospect["status"])

    # Update prospects table
    cur.execute("""
        UPDATE prospects SET
            response_status = ?,
            status = ?,
            signed_up = CASE WHEN ? = 1 THEN 1 ELSE signed_up END,
            free_credits_given = CASE WHEN ? > 0 THEN ? ELSE free_credits_given END,
            raw_notes = CASE WHEN ? IS NOT NULL THEN (COALESCE(raw_notes, '') || '\n' || ?) ELSE raw_notes END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (response_status, new_prospect_status, 1 if signed_up else 0, free_credits, free_credits, notes, notes, prospect_id))

    # Update latest outreach email if replied
    cur.execute("""
        SELECT id FROM outreach_emails WHERE prospect_id = ? ORDER BY id DESC LIMIT 1
    """, (prospect_id,))
    email_row = cur.fetchone()

    email_id = None
    if email_row:
        email_id = email_row["id"]
        email_status = "replied" if response_status in ("interested", "not_interested") else "sent"
        cur.execute("""
            UPDATE outreach_emails SET
                status = ?,
                replied_at = CURRENT_TIMESTAMP,
                notes = CASE WHEN ? IS NOT NULL THEN (COALESCE(notes, '') || ' | ' || ?) ELSE notes END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (email_status, notes, notes, email_id))

        cur.execute("""
            INSERT INTO interaction_logs (outreach_email_id, event_type, details)
            VALUES (?, ?, ?)
        """, (email_id, f"reply_{response_status}", notes or f"Response recorded: {response_status}"))

    conn.commit()
    conn.close()

    # Re-export CSV for tracking visibility
    try:
        from src.storage.sync_prospects import export_prospects_to_csv
        export_prospects_to_csv("data/exports/prospects.csv", db_path)
    except Exception as e:
        logger.warning(f"Could not re-export CSV: {e}")

    return {
        "prospect_id": prospect_id,
        "title": prospect["title"],
        "response_status": response_status,
        "status": new_prospect_status,
        "signed_up": signed_up
    }
