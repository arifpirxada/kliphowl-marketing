"""Deduplication and consolidation utilities for prospects."""

import logging
from src.storage.db import get_db, DEFAULT_DB_PATH
from src.storage.sync_prospects import export_prospects_to_csv

logger = logging.getLogger("dedup")


def deduplicate_prospects(db_path: str = DEFAULT_DB_PATH) -> int:
    """Find prospects with duplicate titles or handles and merge them into the canonical record."""
    conn = get_db(db_path)
    cur = conn.cursor()

    # Find duplicates by normalized title or handle
    cur.execute("SELECT id, title, handle, subscriber_count, primary_email, custom_url, sample_video_url FROM prospects")
    all_prospects = cur.fetchall()

    merged_count = 0
    by_title = {}
    by_handle = {}

    for p in all_prospects:
        t_key = (p["title"] or "").lower().strip()
        h_key = (p["handle"] or "").lower().strip().lstrip("@")
        if t_key:
            by_title.setdefault(t_key, []).append(p)
        if h_key:
            by_handle.setdefault(h_key, []).append(p)

    candidate_groups = list(by_title.values()) + list(by_handle.values())
    seen_merged = set()

    for items in candidate_groups:
        if len(items) <= 1:
            continue

        # Filter out already deleted IDs
        valid_items = [it for it in items if it["id"] not in seen_merged]
        if len(valid_items) <= 1:
            continue

        # Prefer record with official YouTube channel ID (starts with UC)
        canonical = None
        for it in valid_items:
            if it["id"].startswith("UC"):
                canonical = it
                break
        if not canonical:
            canonical = valid_items[0]

        duplicates = [it for it in valid_items if it["id"] != canonical["id"]]

        for dup in duplicates:
            if dup["id"] in seen_merged:
                continue
            seen_merged.add(dup["id"])

            cur.execute("UPDATE videos SET prospect_id = ? WHERE prospect_id = ?", (canonical["id"], dup["id"]))
            cur.execute("UPDATE outreach_emails SET prospect_id = ? WHERE prospect_id = ?", (canonical["id"], dup["id"]))
            
            if dup["primary_email"] and not canonical["primary_email"]:
                cur.execute("UPDATE prospects SET primary_email = ? WHERE id = ?", (dup["primary_email"], canonical["id"]))
            if dup["sample_video_url"] and not canonical["sample_video_url"]:
                cur.execute("UPDATE prospects SET sample_video_url = ? WHERE id = ?", (dup["sample_video_url"], canonical["id"]))

            cur.execute("DELETE FROM prospects WHERE id = ?", (dup["id"],))
            merged_count += 1
            logger.info(f"Merged duplicate '{dup['title']}' ({dup['id']}) into canonical '{canonical['title']}' ({canonical['id']})")

    conn.commit()
    conn.close()

    if merged_count > 0:
        export_prospects_to_csv("data/exports/prospects.csv", db_path)

    return merged_count
