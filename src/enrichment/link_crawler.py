"""External link extraction and secondary website/GitHub email crawler."""

import logging
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
import requests

from src.config import GITHUB_TOKEN
from src.enrichment.email_extractor import extract_emails_from_text, find_primary_email

logger = logging.getLogger("link_crawler")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

# Domains that are platforms, not creator personal sites
EXCLUDED_SITE_DOMAINS = {
    "youtube.com", "youtu.be", "google.com", "amzn.to", "amazon.com",
    "discord.gg", "discord.com", "apple.com", "wikipedia.org",
    "patreon.com", "tiktok.com", "instagram.com", "facebook.com",
    "buymeacoffee.com", "ko-fi.com", "cursor.com", "cloudflare.com",
    "mozilla.org", "rfc-editor.org", "w3.org", "nas.com", "t.me",
    "bit.ly", "shorturl.at", "codeslides.app"
}


def extract_links_from_text(text: str) -> Dict[str, Optional[str]]:
    """Extract Twitter/X, GitHub, LinkedIn, and personal website links from text."""
    if not text:
        return {"twitter": None, "github": None, "linkedin": None, "website": None}

    raw_urls = re.findall(r'https?://[^\s\)\>\]\",]+', text)
    links: Dict[str, Optional[str]] = {
        "twitter": None,
        "github": None,
        "linkedin": None,
        "website": None
    }

    candidate_websites = []

    for url in raw_urls:
        url_clean = url.rstrip("/.,;:)")
        parsed = urlparse(url_clean)
        netloc = parsed.netloc.lower()

        if "x.com" in netloc or "twitter.com" in netloc:
            # Avoid generic twitter intents/share links
            if not any(k in url_clean for k in ["/intent/", "/share", "/hashtag"]):
                links["twitter"] = url_clean
        elif "github.com" in netloc:
            if not any(k in url_clean for k in ["/issues", "/pulls", "/commit"]):
                links["github"] = url_clean
        elif "linkedin.com" in netloc:
            if "/in/" in url_clean or "/company/" in url_clean:
                links["linkedin"] = url_clean
        else:
            # Check if potential personal site
            is_excluded = any(netloc == d or netloc.endswith("." + d) for d in EXCLUDED_SITE_DOMAINS)
            if not is_excluded and len(netloc) > 3:
                candidate_websites.append(url_clean)

    if candidate_websites:
        # Choose root or shortest URL as primary website
        candidate_websites.sort(key=lambda u: (len(urlparse(u).path), len(u)))
        links["website"] = candidate_websites[0]

    return links


def crawl_website_for_email(url: str, timeout: int = 7) -> Optional[str]:
    """Crawl a website homepage and common contact pages to find a business email."""
    if not url:
        return None

    visited: Set[str] = set()
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    pages_to_check = [
        url,
        base_url,
        urljoin(base_url, "/contact"),
        urljoin(base_url, "/contact-us"),
        urljoin(base_url, "/about"),
        urljoin(base_url, "/about-us"),
    ]

    for page in pages_to_check:
        if page in visited:
            continue
        visited.add(page)

        try:
            resp = requests.get(page, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200 and "html" in resp.headers.get("Content-Type", ""):
                # Check for mailto: links first
                mailto_matches = re.findall(r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', resp.text)
                for em in mailto_matches:
                    clean_em = extract_emails_from_text(em)
                    if clean_em:
                        return clean_em[0]

                # Extract emails from body
                emails = extract_emails_from_text(resp.text)
                if emails:
                    return emails[0]
        except Exception:
            continue

    return None


def find_github_email(github_url: str, token: Optional[str] = GITHUB_TOKEN) -> Optional[str]:
    """Look up a developer's public email from their GitHub profile or commit events."""
    if not github_url:
        return None

    # Extract username
    m = re.search(r'github\.com/([a-zA-Z0-9_\-]+)', github_url)
    if not m:
        return None
    username = m.group(1)

    headers = {"User-Agent": "KlipHowl-Marketing-Agent"}
    if token and token != "your_github_token_here":
        headers["Authorization"] = f"token {token}"

    try:
        # 1. Profile check
        resp = requests.get(f"https://api.github.com/users/{username}", headers=headers, timeout=5)
        if resp.status_code == 200:
            user_data = resp.json()
            email = user_data.get("email")
            if email:
                clean = extract_emails_from_text(email)
                if clean:
                    return clean[0]

        # 2. Public commit events check (often reveals git commit author email)
        events_resp = requests.get(f"https://api.github.com/users/{username}/events/public", headers=headers, timeout=5)
        if events_resp.status_code == 200:
            events = events_resp.json()
            for ev in events:
                if ev.get("type") == "PushEvent":
                    commits = ev.get("payload", {}).get("commits", [])
                    for c in commits:
                        author_email = c.get("author", {}).get("email")
                        if author_email and not author_email.endswith("@users.noreply.github.com"):
                            clean = extract_emails_from_text(author_email)
                            if clean:
                                return clean[0]
    except Exception as e:
        logger.debug(f"GitHub email lookup failed for {username}: {e}")

    return None
