"""Automated YouTube Prospect Discovery & Staging Pipeline.

STRICT RULE:
This module NEVER writes directly into data/marketing.db.
It writes discovered candidates to a review Markdown file (data/discovery_staging.md).
The human operator reviews candidates, deletes unwanted entries, adjusts match scores,
and then runs `uv run marketing import-staging` to merge approved prospects into the DB.
"""

import argparse
import logging
import os
import re
from typing import Dict, List, Optional, Set

from src.discovery.yt_client import YouTubeClient
from src.enrichment.email_extractor import find_primary_email
from src.enrichment.link_crawler import extract_links_from_text, crawl_website_for_email
from src.storage.db import get_db, DEFAULT_DB_PATH

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("discovery")

DEFAULT_STAGING_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "discovery_staging.md"
)

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


def format_sub_display(subs: int) -> str:
    """Format subscriber count for markdown display (e.g. 124k subs)."""
    if subs >= 1_000_000:
        return f"{subs / 1_000_000:.1f}M subs"
    elif subs >= 1_000:
        return f"{int(subs / 1_000)}k subs"
    return f"{subs} subs"


def format_markdown_entry(ch_data: dict) -> str:
    """Format a single candidate channel as an Obsidian/GitHub callout block."""
    title = ch_data["title"]
    links = []
    if ch_data.get("sample_video_url"):
        links.append(f"[YouTube Video]({ch_data['sample_video_url']})")
    if ch_data.get("custom_url"):
        links.append(f"[YouTube Channel]({ch_data['custom_url']})")
    if ch_data.get("twitter_url"):
        links.append(f"[X]({ch_data['twitter_url']})")
    if ch_data.get("website_url"):
        links.append(f"[Website]({ch_data['website_url']})")

    links_str = "  ".join(links) if links else "None"
    subs_str = format_sub_display(ch_data["subscriber_count"]) if ch_data["subscriber_count"] else "-"
    match_str = ch_data.get("match_level", "medium")

    # Header callout color/type
    callout = "warning"
    if match_str == "high":
        callout = "tip"
    elif match_str == "low":
        callout = "note"

    lines = [
        f"> [!{callout}] {title}",
        "",
        f"**Links:** {links_str}",
        f"**Type:** YouTuber ({subs_str})",
        f"**Size:** {subs_str}",
        f"**Match:** {match_str}",
    ]

    if ch_data.get("primary_email"):
        lines.append(f"**Email:** {ch_data['primary_email']}")

    if ch_data.get("discovered_via"):
        lines.append(f"**Discovered Via:** {ch_data['discovered_via']}")

    if ch_data.get("video_title"):
        lines.append(f"**Sample Video:** {ch_data['video_title']}")

    lines.extend([
        "**Outreached?:**",
        "**Response:**",
        "**Signedup?:**",
        "**Free Credits?:**",
        "",
    ])

    return "\n".join(lines)


def discover_prospects_to_staging(
    queries: Optional[List[str]] = None,
    min_subs: int = 5_000,
    max_subs: int = 350_000,
    max_queries: int = 2,
    output_path: str = DEFAULT_STAGING_PATH,
    db_path: str = DEFAULT_DB_PATH,
) -> dict:
    """Run search queries, filter by subscriber sweet spot, enrich emails, and write to staging markdown."""
    client = YouTubeClient()

    # Read existing channel IDs and titles from DB to prevent re-discovering known channels
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, LOWER(TRIM(title)) as t, handle FROM prospects")
    existing_rows = cur.fetchall()
    conn.close()

    existing_ids: Set[str] = {r["id"] for r in existing_rows}
    existing_titles: Set[str] = {r["t"] for r in existing_rows if r["t"]}
    existing_handles: Set[str] = {(r["handle"] or "").lower().strip().lstrip("@") for r in existing_rows if r["handle"]}

    queries_to_run = (queries or DEFAULT_QUERIES)[:max_queries]
    logger.info(f"Searching YouTube across {len(queries_to_run)} queries (Subs: {min_subs:,} to {max_subs:,})...")

    candidate_channels: Dict[str, dict] = {}

    # Step 1: Run search queries
    for q in queries_to_run:
        logger.info(f"Querying YouTube for: '{q}' (Cost: 100 quota units)...")
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
            channel_title = snippet.get("channelTitle", "").strip().lower()

            if not channel_id:
                continue
            if channel_id in existing_ids or channel_title in existing_titles:
                continue
            if channel_id not in candidate_channels:
                candidate_channels[channel_id] = {
                    "video_id": video_id,
                    "video_title": video_title,
                    "query_keyword": q,
                }

    logger.info(f"Found {len(candidate_channels)} unique unvetted candidate channels.")
    if not candidate_channels:
        return {"scanned": 0, "qualified": 0, "emails_found": 0, "quota_used": client.total_quota_used, "output_path": output_path}

    # Step 2: Batch lookup details
    channel_ids = list(candidate_channels.keys())
    channel_details = client.get_channels_by_id(channel_ids)

    qualified_candidates = []
    emails_found_count = 0

    # Step 3: Filter and enrich contact info
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

        # Check existing handle
        clean_h = (handle or "").lower().strip().lstrip("@")
        if clean_h and clean_h in existing_handles:
            continue

        # Filter by subscriber count
        if subs > 0 and (subs < min_subs or subs > max_subs):
            continue

        cand_meta = candidate_channels[cid]
        sample_video_url = f"https://www.youtube.com/watch?v={cand_meta['video_id']}" if cand_meta.get("video_id") else None

        desc_lower = description.lower()
        if any(k in desc_lower for k in ["animation", "diagram", "visual", "system design", "architecture"]):
            match_level = "high"
        else:
            match_level = "medium"

        email = find_primary_email(description)
        links = extract_links_from_text(description)
        twitter = links.get("twitter")
        github = links.get("github")
        website = links.get("website")

        if not email and website:
            site_email = crawl_website_for_email(website, timeout=4)
            if site_email:
                email = site_email

        if email:
            emails_found_count += 1

        qualified_candidates.append({
            "id": cid,
            "title": title,
            "handle": handle,
            "custom_url": custom_url,
            "sample_video_url": sample_video_url,
            "video_title": cand_meta.get("video_title"),
            "subscriber_count": subs,
            "video_count": video_count,
            "view_count": view_count,
            "country": country,
            "description": description,
            "primary_email": email,
            "twitter_url": twitter,
            "github_url": github,
            "website_url": website,
            "match_level": match_level,
            "discovered_via": cand_meta["query_keyword"],
        })

    # Step 4: Write to Markdown Staging file (never write directly to DB!)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    header_block = (
        "# Discovered Prospects for Review\n\n"
        "> [!tip] Review Instructions\n"
        "> 1. Review each candidate below before adding to the database.\n"
        "> 2. Delete any entries you do not wish to target.\n"
        "> 3. Adjust **Match:** (`low`, `medium`, `high`) or edit notes as needed.\n"
        "> 4. When ready, merge approved prospects into `data/marketing.db` by running:\n"
        ">    ```bash\n"
        ">    uv run marketing import-staging\n"
        ">    ```\n\n"
    )

    entries_md = "\n".join(format_markdown_entry(c) for c in qualified_candidates)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header_block + entries_md)

    summary = {
        "queries_run": len(queries_to_run),
        "channels_scanned": len(candidate_channels),
        "qualified_staged": len(qualified_candidates),
        "emails_found": emails_found_count,
        "quota_used": client.total_quota_used,
        "output_path": output_path
    }
    logger.info(f"Discovery complete! Staged {len(qualified_candidates)} prospects in {output_path}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Discover tech YouTube explainers and stage for review")
    parser.add_argument("--query", help="Specific search query")
    parser.add_argument("--queries", type=int, default=1, help="Number of default queries to execute (default: 1)")
    parser.add_argument("--min-subs", type=int, default=5000, help="Minimum subscriber threshold (default: 5000)")
    parser.add_argument("--max-subs", type=int, default=350000, help="Maximum subscriber threshold (default: 350000)")
    parser.add_argument("--output", default=DEFAULT_STAGING_PATH, help="Staging markdown output path")

    args = parser.parse_args()
    queries = [args.query] if args.query else None

    summary = discover_prospects_to_staging(
        queries=queries,
        min_subs=args.min_subs,
        max_subs=args.max_subs,
        max_queries=args.queries,
        output_path=args.output,
    )
    print("\n✓ Discovery complete! Staged for review:")
    print(f"  • Channels scanned: {summary['channels_scanned']}")
    print(f"  • Staged for human review: {summary['qualified_staged']}")
    print(f"  • Business emails discovered: {summary['emails_found']}")
    print(f"  • Quota units used: {summary['quota_used']}")
    print(f"  • Review file: {summary['output_path']}\n")
    print("👉 Open data/discovery_staging.md, delete unwanted channels, and run:")
    print("   uv run marketing import-staging")


if __name__ == "__main__":
    main()
