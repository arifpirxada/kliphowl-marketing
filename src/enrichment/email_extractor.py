"""Email extraction utilities for YouTube descriptions and text."""

import re
from typing import List, Optional

# Regular expression for matching email addresses
# Excludes common image extensions or false positives
EMAIL_REGEX = re.compile(
    r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
)

# Common generic/platform emails to ignore
IGNORED_DOMAINS = {
    "youtube.com",
    "google.com",
    "googleapis.com",
    "example.com",
    "domain.com",
    "sentry.io",
}

# Image-like false positives that match regex
IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"
}


def extract_emails_from_text(text: str) -> List[str]:
    """Extract and validate clean email addresses from freeform text/descriptions."""
    if not text:
        return []

    # Clean text to handle common obfuscations (e.g. "name [at] domain [dot] com")
    normalized = text
    normalized = re.sub(r'\[at\]|\(at\)', '@', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\[dot\]|\(dot\)', '.', normalized, flags=re.IGNORECASE)

    raw_matches = EMAIL_REGEX.findall(normalized)
    valid_emails = []

    for email in raw_matches:
        email = email.strip().strip(".,;:()<>[]\"'").lower()
        if any(email.endswith(ext) for ext in IGNORED_EXTENSIONS):
            continue
        domain = email.split("@")[-1]
        if domain in IGNORED_DOMAINS:
            continue
        if len(email) > 6 and "." in domain:
            if email not in valid_emails:
                valid_emails.append(email)

    return valid_emails


def find_primary_email(text: str) -> Optional[str]:
    """Find the most likely business inquiry email from text."""
    emails = extract_emails_from_text(text)
    if not emails:
        return None

    # Prioritize business/contact keywords if multiple emails found
    business_keywords = ["business", "inquiries", "inquiry", "contact", "sponsor", "mgmt", "management"]
    lines = text.splitlines()
    for line in lines:
        for kw in business_keywords:
            if kw in line.lower():
                for em in emails:
                    if em in line.lower():
                        return em

    return emails[0]
