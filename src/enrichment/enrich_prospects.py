"""Enrich prospects in marketing.db using YouTube Data API v3 and Email Extraction."""

import logging
from typing import Dict, List, Set
from urllib.parse import parse_qs, urlparse

from src.discovery.yt_client import YouTubeClient
from src.enrichment.email_extractor import find_primary_email, extract_emails_from_text
from src.storage.db import get_db, DEFAULT_DB_PATH
from src.storage.sync_prospects import extract_video_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("enricher")


def enrich_all_prospects(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Enrich all prospects in the database with YouTube metadata and emails."""
    client = YouTubeClient()
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id, title, handle, custom_url, sample_video_url, primary_email FROM prospects")
    prospects = cur.fetchall()

    logger.info(f"Loaded {len(prospects)} prospects from database.")

    # 1. Collect video IDs to batch fetch
    video_map: Dict[str, str] = {}  # video_id -> prospect_id
    for p in prospects:
        if p["sample_video_url"]:
            vid = extract_video_id(p["sample_video_url"])
            if vid:
                video_map[vid] = p["id"]

    logger.info(f"Resolving {len(video_map)} YouTube videos in batch...")
    video_items = client.get_videos(list(video_map.keys()))

    # Map prospect_id -> channel_id
    prospect_channel_map: Dict[str, str] = {}
    channel_video_data: Dict[str, dict] = {}

    for v in video_items:
        vid = v["id"]
        snippet = v.get("snippet", {})
        stats = v.get("statistics", {})
        prospect_id = video_map.get(vid)
        if not prospect_id:
            continue

        channel_id = snippet.get("channelId")
        if channel_id:
            prospect_channel_map[prospect_id] = channel_id

        # Insert or update video in DB
        cur.execute("""
            INSERT INTO videos (video_id, prospect_id, title, published_at, view_count, description)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                published_at = excluded.published_at,
                view_count = excluded.view_count,
                description = excluded.description
        """, (
            vid,
            prospect_id,
            snippet.get("title", ""),
            snippet.get("publishedAt"),
            int(stats.get("viewCount", 0)),
            snippet.get("description", "")
        ))

    conn.commit()

    # 2. Gather unique channel IDs and handles to fetch
    channel_ids: Set[str] = set(prospect_channel_map.values())
    handles_to_fetch: Dict[str, str] = {}  # handle -> prospect_id

    for p in prospects:
        pid = p["id"]
        if pid not in prospect_channel_map:
            # Check handle
            if p["handle"] and "@" in p["handle"]:
                handles_to_fetch[p["handle"]] = pid
            elif p["custom_url"] and "@" in p["custom_url"]:
                h = "@" + p["custom_url"].split("@")[-1].split("/")[0]
                handles_to_fetch[h] = pid

    logger.info(f"Fetching details for {len(channel_ids)} channels by ID and {len(handles_to_fetch)} by handle...")
    
    channel_items = client.get_channels_by_id(list(channel_ids))
    channel_by_id_dict = {c["id"]: c for c in channel_items}

    # Fetch handles individually
    channel_by_handle_dict = {}
    for h, pid in handles_to_fetch.items():
        try:
            c = client.get_channel_by_handle(h)
            if c:
                channel_by_handle_dict[h] = c
                channel_by_id_dict[c["id"]] = c
                prospect_channel_map[pid] = c["id"]
        except Exception as e:
            logger.warning(f"Failed to fetch channel for handle {h}: {e}")

    # 3. Update prospects table with channel metadata & email
    emails_found_count = 0
    channels_updated_count = 0

    for p in prospects:
        pid = p["id"]
        cid = prospect_channel_map.get(pid)
        channel_data = channel_by_id_dict.get(cid) if cid else None

        if not channel_data:
            continue

        snippet = channel_data.get("snippet", {})
        stats = channel_data.get("statistics", {})
        branding = channel_data.get("brandingSettings", {}).get("channel", {})

        subs = int(stats.get("subscriberCount", 0))
        video_count = int(stats.get("videoCount", 0))
        view_count = int(stats.get("viewCount", 0))
        description = snippet.get("description", "")
        country = snippet.get("country")
        custom_url = f"https://www.youtube.com/{snippet.get('customUrl', '')}" if snippet.get('customUrl') else p["custom_url"]

        # Search for email in description
        extracted_email = find_primary_email(description)
        email_source = "yt_description" if extracted_email else p.get("email_source")
        final_email = extracted_email or p.get("primary_email")

        if extracted_email and not p.get("primary_email"):
            emails_found_count += 1
            logger.info(f"✨ Found email for {p['title']}: {extracted_email}")

        cur.execute("""
            UPDATE prospects SET
                subscriber_count = CASE WHEN ? > 0 THEN ? ELSE subscriber_count END,
                video_count = ?,
                view_count = ?,
                country = COALESCE(?, country),
                description = COALESCE(?, description),
                custom_url = COALESCE(?, custom_url),
                primary_email = COALESCE(?, primary_email),
                email_source = COALESCE(?, email_source),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            subs, subs,
            video_count,
            view_count,
            country,
            description,
            custom_url,
            final_email,
            email_source,
            pid
        ))
        channels_updated_count += 1

    conn.commit()
    conn.close()

    summary = {
        "channels_updated": channels_updated_count,
        "emails_found": emails_found_count,
        "quota_used": client.total_quota_used
    }
    logger.info(f"Enrichment completed! Summary: {summary}")
    return summary


if __name__ == "__main__":
    enrich_all_prospects()
