"""Database repository for cold outreach candidates, email drafts, and tracking."""

import logging
import os
import re
from typing import Dict, List, Optional

from src.storage.db import get_db, DEFAULT_DB_PATH

logger = logging.getLogger("outreach_repo")


def slugify(text: str) -> str:
    """Generate a clean slug for file naming (e.g. 'Caleb Writes Code' -> 'caleb_writes_code')."""
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text.lower()).strip('_')
    return text or "prospect"


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


def get_all_drafts(db_path: str = DEFAULT_DB_PATH) -> List[Dict]:
    """Retrieve all email drafts from SQLite joined with prospect details."""
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            e.id, e.prospect_id, p.title as channel_title, e.recipient_email,
            e.subject_line, e.status, e.draft_file_path, e.notes,
            e.created_at, e.updated_at
        FROM outreach_emails e
        JOIN prospects p ON e.prospect_id = p.id
        ORDER BY e.updated_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows
