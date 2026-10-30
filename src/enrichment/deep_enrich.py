"""Secondary enrichment: Link extraction, website crawling, and manual captcha queue."""

import logging
from typing import Dict, List
from urllib.parse import urlparse

from src.enrichment.link_crawler import (
    extract_links_from_text,
    crawl_website_for_email,
    find_github_email
)
from src.storage.db import get_db, DEFAULT_DB_PATH
from src.storage.sync_prospects import export_prospects_to_csv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("deep_enrich")


def run_deep_enrichment(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Extract social links, crawl creator websites, and check GitHub for missing emails."""
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT p.id, p.title, p.handle, p.custom_url, p.primary_email, p.email_source,
               p.twitter_url, p.github_url, p.website_url, p.description,
               v.description as video_desc
        FROM prospects p
        LEFT JOIN videos v ON p.id = v.prospect_id
    """)
    prospects = cur.fetchall()

    links_discovered = 0
    new_emails_found = 0

    for p in prospects:
        combined_text = f"{p['description'] or ''} {p['video_desc'] or ''}"
        extracted = extract_links_from_text(combined_text)

        twitter = p["twitter_url"] or extracted.get("twitter")
        github = p["github_url"] or extracted.get("github")
        website = p["website_url"] or extracted.get("website")

        # Check if links changed
        if twitter != p["twitter_url"] or github != p["github_url"] or website != p["website_url"]:
            links_discovered += 1

        primary_email = p["primary_email"]
        email_source = p["email_source"]

        # If email is missing, crawl website or GitHub
        if not primary_email:
            if website:
                logger.info(f"Crawling website for {p['title']}: {website}")
                site_email = crawl_website_for_email(website)
                if site_email:
                    primary_email = site_email
                    email_source = "website"
                    new_emails_found += 1
                    logger.info(f"✨ Found website email for {p['title']}: {site_email}")

            if not primary_email and github:
                logger.info(f"Checking GitHub for {p['title']}: {github}")
                gh_email = find_github_email(github)
                if gh_email:
                    primary_email = gh_email
                    email_source = "github"
                    new_emails_found += 1
                    logger.info(f"✨ Found GitHub email for {p['title']}: {gh_email}")

        cur.execute("""
            UPDATE prospects SET
                twitter_url = ?,
                github_url = ?,
                website_url = ?,
                primary_email = ?,
                email_source = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (twitter, github, website, primary_email, email_source, p["id"]))

    conn.commit()
    conn.close()

    # Re-export CSV
    export_prospects_to_csv("data/exports/prospects.csv", db_path)

    summary = {
        "links_updated": links_discovered,
        "new_emails_found": new_emails_found,
    }
    logger.info(f"Deep enrichment complete: {summary}")
    return summary


def get_captcha_queue(db_path: str = DEFAULT_DB_PATH, min_match: str = "medium") -> List[dict]:
    """Return high-priority prospects who need a quick 1-click manual captcha check on YouTube."""
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, handle, custom_url, subscriber_count, match_level
        FROM prospects
        WHERE (primary_email IS NULL OR primary_email = '')
          AND custom_url LIKE '%youtube.com%'
        ORDER BY subscriber_count DESC
    """)
    rows = cur.fetchall()
    conn.close()

    queue = []
    for r in rows:
        url = r["custom_url"]
        # Format about URL
        if "@" in url:
            handle = "@" + url.split("@")[-1].split("/")[0]
            about_url = f"https://www.youtube.com/{handle}/about"
        elif "/channel/" in url:
            cid = url.split("/channel/")[-1].split("/")[0]
            about_url = f"https://www.youtube.com/channel/{cid}/about"
        else:
            about_url = f"{url.rstrip('/')}/about"

        queue.append({
            "id": r["id"],
            "title": r["title"],
            "match": r["match_level"],
            "subs": r["subscriber_count"],
            "about_url": about_url
        })

    return queue
