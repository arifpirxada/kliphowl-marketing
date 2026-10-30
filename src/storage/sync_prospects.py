"""Bidirectional synchronization and parsing between prospects.md and SQLite database."""

import csv
import os
import re
import sqlite3
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from src.storage.db import get_db, DEFAULT_DB_PATH


def parse_sub_count(text: str) -> Optional[int]:
    """Parse subscriber text like '124k subs', '1.5M subs', '64 subs', '20 m subs' into an integer."""
    if not text:
        return None
    match = re.search(r'([\d\.]+)\s*([kmb])?\s*(?:subs?|subscribers?)?', text, re.IGNORECASE)
    if not match:
        return None
    val_str, unit = match.group(1), (match.group(2) or '').lower()
    try:
        val = float(val_str)
        if unit == 'k':
            return int(val * 1_000)
        elif unit == 'm':
            return int(val * 1_000_000)
        elif unit == 'b':
            return int(val * 1_000_000_000)
        return int(val)
    except ValueError:
        return None


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from watch URL or short link."""
    parsed = urlparse(url)
    if parsed.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed.path == '/watch':
            qs = parse_qs(parsed.query)
            return qs.get('v', [None])[0]
        elif parsed.path.startswith('/shorts/'):
            return parsed.path.split('/')[2]
    elif parsed.hostname == 'youtu.be':
        return parsed.path.lstrip('/')
    return None


def parse_prospects_markdown(md_path: str) -> List[Dict]:
    """Parse prospects.md content and return structured list of prospect dictionaries."""
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r'>\s*\[!(?:warning|tip|info|note)\]\s*', content)
    prospects = []

    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        header = lines[0].strip()
        if 'template' in header.lower():
            continue

        body = '\n'.join(lines[1:])

        # Extract title and possible index from header e.g. "theodd1sout (8)" or "Caleb Writes Code (13)"
        header_match = re.match(r'^(.*?)(?:\s*\((\d+)\))?$', header)
        if header_match:
            title = header_match.group(1).strip()
            order_index = header_match.group(2)
        else:
            title = header
            order_index = None

        # Links
        yt_links = re.findall(r'https?://(?:www\.)?youtube\.com/[^\s\)\>]+', body)
        x_links = re.findall(r'https?://(?:www\.)?(?:x|twitter)\.com/[^\s\)\>]+', body)

        # Separate video URLs and channel URLs
        sample_video_url = None
        custom_url = None
        handle = None

        for link in yt_links:
            vid = extract_video_id(link)
            if vid:
                sample_video_url = link
            elif '@' in link:
                custom_url = link
                h_match = re.search(r'@([a-zA-Z0-9_\-\.]+)', link)
                if h_match:
                    handle = f"@{h_match.group(1)}"
            elif not custom_url:
                custom_url = link

        twitter_url = x_links[0] if x_links else None
        if not handle and twitter_url:
            x_match = re.search(r'com/([a-zA-Z0-9_]+)', twitter_url)
            if x_match:
                handle = f"@{x_match.group(1)}"

        # Metadata fields
        type_m = re.search(r'\*\*Type:\*\*[ \t]*([^\r\n]*)', body, re.IGNORECASE)
        type_val = type_m.group(1).strip() if type_m else 'youtuber'

        size_m = re.search(r'\*\*Size:\*\*[ \t]*([^\r\n]*)', body, re.IGNORECASE)
        size_val = size_m.group(1).strip() if size_m else None

        # Try to parse sub count from size or type string
        subs = None
        if size_val:
            subs = parse_sub_count(size_val)
        if subs is None and type_val:
            subs = parse_sub_count(type_val)

        match_m = re.search(r'\*\*Match:\*\*[ \t]*([^\r\n]*)', body, re.IGNORECASE)
        match_val = match_m.group(1).strip().lower() if match_m else 'medium'
        if not match_val:
            match_val = 'medium'

        # Funnel tracking
        outreach_m = re.search(r'\*\*Outreached\?:\*\*[ \t]*([^\r\n]*)', body, re.IGNORECASE)
        outreached_str = outreach_m.group(1).strip() if outreach_m else ''
        outreached = 1 if outreached_str.lower() in ('yes', 'true', '1', 'done') else 0

        response_m = re.search(r'\*\*Response:\*\*[ \t]*([^\r\n]*)', body, re.IGNORECASE)
        response_str = response_m.group(1).strip() if response_m else 'none'

        signedup_m = re.search(r'\*\*Signedup\?:\*\*[ \t]*([^\r\n]*)', body, re.IGNORECASE)
        signedup_str = signedup_m.group(1).strip() if signedup_m else ''
        signed_up = 1 if signedup_str.lower() in ('yes', 'true', '1') else 0

        credits_m = re.search(r'\*\*Free Credits\?:\*\*[ \t]*([^\r\n]*)', body, re.IGNORECASE)
        credits_str = credits_m.group(1).strip() if credits_m else ''
        free_credits = int(credits_str) if credits_str.isdigit() else (10 if credits_str.lower() == 'yes' else 0)

        # ID generation
        clean_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', title.lower()).strip('_')
        if handle:
            prospect_id = f"yt:{handle}" if yt_links else f"x:{handle}"
        elif sample_video_url:
            vid = extract_video_id(sample_video_url)
            prospect_id = f"yt:vid_{vid}" if vid else f"lead_{clean_slug}"
        elif custom_url:
            prospect_id = f"yt:{clean_slug}"
        elif twitter_url:
            prospect_id = f"x:{clean_slug}"
        else:
            prospect_id = f"lead_{clean_slug}"

        prospects.append({
            'id': prospect_id,
            'title': title,
            'handle': handle,
            'custom_url': custom_url or (yt_links[0] if yt_links else (twitter_url or '')),
            'sample_video_url': sample_video_url,
            'prospect_type': type_val,
            'size_tier': size_val or (type_val if 'subs' in type_val.lower() else None),
            'subscriber_count': subs or 0,
            'twitter_url': twitter_url,
            'match_level': match_val,
            'outreached': outreached,
            'response_status': response_str or 'none',
            'signed_up': signed_up,
            'free_credits_given': free_credits,
            'raw_notes': body.strip()
        })

    return prospects


def import_prospects_to_db(md_path: str, db_path: str = DEFAULT_DB_PATH) -> int:
    """Parse markdown file and upsert all prospects into SQLite database."""
    prospects = parse_prospects_markdown(md_path)
    conn = get_db(db_path)
    cur = conn.cursor()

    count = 0
    for p in prospects:
        cur.execute("""
            INSERT INTO prospects (
                id, title, handle, custom_url, sample_video_url, prospect_type,
                size_tier, subscriber_count, twitter_url, match_level,
                outreached, response_status, signed_up, free_credits_given, raw_notes, updated_at
            ) VALUES (
                :id, :title, :handle, :custom_url, :sample_video_url, :prospect_type,
                :size_tier, :subscriber_count, :twitter_url, :match_level,
                :outreached, :response_status, :signed_up, :free_credits_given, :raw_notes, CURRENT_TIMESTAMP
            )
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                handle = COALESCE(excluded.handle, prospects.handle),
                custom_url = COALESCE(excluded.custom_url, prospects.custom_url),
                sample_video_url = COALESCE(excluded.sample_video_url, prospects.sample_video_url),
                prospect_type = excluded.prospect_type,
                size_tier = COALESCE(excluded.size_tier, prospects.size_tier),
                subscriber_count = CASE WHEN excluded.subscriber_count > 0 THEN excluded.subscriber_count ELSE prospects.subscriber_count END,
                twitter_url = COALESCE(excluded.twitter_url, prospects.twitter_url),
                match_level = excluded.match_level,
                outreached = excluded.outreached,
                response_status = excluded.response_status,
                signed_up = excluded.signed_up,
                free_credits_given = excluded.free_credits_given,
                raw_notes = excluded.raw_notes,
                updated_at = CURRENT_TIMESTAMP
        """, p)
        count += 1

    conn.commit()
    conn.close()
    return count


def export_prospects_to_csv(csv_path: str, db_path: str = DEFAULT_DB_PATH) -> int:
    """Export all prospects from SQLite database to a CSV file."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM prospects ORDER BY subscriber_count DESC, title ASC")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return 0

    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    fieldnames = list(rows[0].keys())

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)
