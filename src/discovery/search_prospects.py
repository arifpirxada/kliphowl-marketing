"""Automated YouTube Prospect Discovery & Qualification Pipeline."""

import logging
from typing import Dict, List, Optional, Set

from src.discovery.yt_client import YouTubeClient
from src.enrichment.email_extractor import find_primary_email
from src.enrichment.link_crawler import extract_links_from_text, crawl_website_for_email
from src.storage.db import get_db, DEFAULT_DB_PATH
from src.storage.sync_prospects import export_prospects_to_csv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("discovery")

# Default targeted search queries for tech explainers who use animations/diagrams
DEFAULT_QUERIES = [
    "system design animated",
    "microservices architecture visual guide",
    "how redis works animated",
    "database indexing visual guide",
    "http protocol explained animation",
    "docker container architecture explained",
    "kafka explained visually",
    "oauth2 explained step by step",
]


def discover_prospects(
    queries: Optional[List[str]] = None,
    min_subs: int = 5_000,
    max_subs: int = 350_000,
    max_queries: int = 3,
    db_path: str = DEFAULT_DB_PATH
) -> dict:
    """Run search queries, filter by subscriber sweet spot, enrich emails, and save to DB."""
    client = YouTubeClient()
    conn = get_db(db_path)
    cur = conn.cursor()

    # Load existing channel IDs to avoid duplicate work
    cur.execute("SELECT id FROM prospects")
    existing_ids: Set[str] = {r["id"] for r in cur.fetchall()}

    queries_to_run = (queries or DEFAULT_QUERIES)[:max_queries]
    logger.info(f"Starting discovery across {len(queries_to_run)} search queries (Subscribers: {min_subs:,} to {max_subs:,})...")

    candidate_channels: Dict[str, dict] = {}  # channel_id -> {sample_video_id, sample_video_title}

    # Step 1: Run search queries to find candidate videos and channels
    for q in queries_to_run:
        logger.info(f"Searching YouTube for: '{q}' (Cost: 100 quota units)...")
        try:
            items = client.search(query=q, max_results=50, type_="video")
        except Exception as e:
            logger.error(f"Search failed for '{q}': {e}")
            continue

        for item in items:
            snippet = item.get("snippet", {})
            channel_id = snippet.get("channelId")
            video_id = item.get("id", {}).get("videoId")
            video_title = snippet.get("title", "")

            # If new channel not already in DB or candidate list
            if channel_id and channel_id not in existing_ids and channel_id not in candidate_channels:
                candidate_channels[channel_id] = {
                    "video_id": video_id,
                    "video_title": video_title,
                    "query_keyword": q,
                }

    logger.info(f"Found {len(candidate_channels)} unique new channels to qualify.")
    if not candidate_channels:
        conn.close()
        return {"scanned": 0, "qualified": 0, "emails_found": 0, "quota_used": client.total_quota_used}

    # Step 2: Batch lookup channel details (Cost: 1 quota unit per 50 channels)
    channel_ids = list(candidate_channels.keys())
    channel_details = client.get_channels_by_id(channel_ids)
    logger.info(f"Retrieved full details for {len(channel_details)} channels.")

    qualified_count = 0
    emails_found_count = 0

    # Step 3: Filter, enrich contact info, and store
    for ch in channel_details:
        cid = ch["id"]
        snippet = ch.get("snippet", {})
        stats = ch.get("statistics", {})

        subs = int(stats.get("subscriberCount", 0))
        video_count = int(stats.get("videoCount", 0))
        view_count = int(stats.get("viewCount", 0))
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        country = snippet.get("country")
        custom_url_raw = snippet.get("customUrl", "")
        handle = f"@{custom_url_raw}" if custom_url_raw and not custom_url_raw.startswith("@") else custom_url_raw
        custom_url = f"https://www.youtube.com/{handle}" if handle else f"https://www.youtube.com/channel/{cid}"

        # Qualification: Subscriber Sweet Spot
        # If subscriberCount is 0, they might have hidden it (or brand new channel)
        if subs > 0 and (subs < min_subs or subs > max_subs):
            continue

        qualified_count += 1
        cand_meta = candidate_channels[cid]
        sample_video_url = f"https://www.youtube.com/watch?v={cand_meta['video_id']}" if cand_meta.get("video_id") else None

        # Determine match score based on query & keywords
        desc_lower = description.lower()
        if any(k in desc_lower for k in ["animation", "diagram", "visual", "system design", "architecture"]):
            match_level = "high"
        else:
            match_level = "medium"

        # Email & link extraction
        email = find_primary_email(description)
        email_source = "yt_description" if email else None

        links = extract_links_from_text(description)
        twitter = links.get("twitter")
        github = links.get("github")
        website = links.get("website")

        # If email not in description but website exists, quick crawl
        if not email and website:
            site_email = crawl_website_for_email(website, timeout=5)
            if site_email:
                email = site_email
                email_source = "website"

        if email:
            emails_found_count += 1
            logger.info(f"✨ Found email for newly qualified prospect {title}: {email}")

        # Insert Prospect into DB
        cur.execute("""
            INSERT INTO prospects (
                id, title, handle, custom_url, sample_video_url, prospect_type,
                subscriber_count, video_count, view_count, country, description,
                primary_email, email_source, twitter_url, github_url, website_url,
                niche_category, match_level, status, qualification_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                subscriber_count = excluded.subscriber_count,
                video_count = excluded.video_count,
                view_count = excluded.view_count,
                primary_email = COALESCE(excluded.primary_email, prospects.primary_email),
                email_source = COALESCE(excluded.email_source, prospects.email_source),
                twitter_url = COALESCE(excluded.twitter_url, prospects.twitter_url),
                github_url = COALESCE(excluded.github_url, prospects.github_url),
                website_url = COALESCE(excluded.website_url, prospects.website_url),
                updated_at = CURRENT_TIMESTAMP
        """, (
            cid,
            title,
            handle,
            custom_url,
            sample_video_url,
            "youtuber",
            subs,
            video_count,
            view_count,
            country,
            description,
            email,
            email_source,
            twitter,
            github,
            website,
            cand_meta["query_keyword"],
            match_level,
            "qualified",
            f"Discovered via search: '{cand_meta['query_keyword']}'"
        ))

        # Insert Candidate Video into videos table
        if cand_meta.get("video_id"):
            cur.execute("""
                INSERT INTO videos (video_id, prospect_id, title)
                VALUES (?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET title = excluded.title
            """, (cand_meta["video_id"], cid, cand_meta["video_title"]))

    conn.commit()
    conn.close()

    # Re-export CSV
    export_prospects_to_csv("data/exports/prospects.csv", db_path)

    summary = {
        "queries_run": len(queries_to_run),
        "channels_scanned": len(candidate_channels),
        "qualified_added": qualified_count,
        "emails_found": emails_found_count,
        "quota_used": client.total_quota_used,
    }
    logger.info(f"Discovery complete! Summary: {summary}")
    return summary


if __name__ == "__main__":
    discover_prospects(max_queries=2)
