"""Outreach Draft Generator & Markdown Writer."""

import argparse
import logging
import os
import re
from datetime import date
from typing import Dict, List, Optional

from src.outreach.prompt_builder import build_prospect_prompt_bundle
from src.outreach.repository import (
    get_outreach_candidates,
    save_email_draft,
    slugify,
    get_all_drafts
)
from src.storage.db import DEFAULT_DB_PATH

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("outreach_gen")

DRAFTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "outreach",
    "drafts"
)


def write_draft_markdown(
    prospect: Dict,
    subject: str,
    body: str,
    custom_instruction: str,
    drafts_dir: str = DRAFTS_DIR,
    db_path: str = DEFAULT_DB_PATH
) -> str:
    """Write an outreach email draft to outreach/drafts/{slug}.md and save to database."""
    os.makedirs(drafts_dir, exist_ok=True)
    slug = slugify(prospect["title"])
    file_path = os.path.join(drafts_dir, f"{slug}.md")

    # Clean subject and body
    clean_subj = subject.strip().replace("### Subject:", "").strip()
    clean_body = body.strip().replace("### Body:", "").strip()

    frontmatter = f"""---
prospect_id: "{prospect['id']}"
channel_title: "{prospect['title']}"
recipient_email: "{prospect['primary_email']}"
status: "ready_for_review"
date_drafted: "{date.today().isoformat()}"
referenced_video: "{prospect.get('video_title') or ''}"
sample_video_url: "{prospect.get('sample_video_url') or ''}"
custom_instruction: "{custom_instruction}"
---

### Subject:
{clean_subj}

### Body:
{clean_body}
"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(frontmatter)

    # Save to SQLite database
    save_email_draft(
        prospect_id=prospect["id"],
        recipient_email=prospect["primary_email"],
        subject=clean_subj,
        body_markdown=clean_body,
        referenced_video_id=prospect.get("video_id"),
        personalized_hook=prospect.get("video_title"),
        custom_instruction=custom_instruction,
        draft_file_path=file_path,
        db_path=db_path
    )

    logger.info(f"Saved email draft for {prospect['title']} ➔ {file_path}")
    return file_path


def prepare_candidate_bundles(
    instruction: str,
    target: Optional[str] = None,
    limit: Optional[int] = None,
    db_path: str = DEFAULT_DB_PATH
) -> List[Dict]:
    """Gather all eligible candidates and build their AI prompt bundles."""
    candidates = get_outreach_candidates(db_path=db_path, target=target, limit=limit)
    bundles = []
    for c in candidates:
        bundles.append(build_prospect_prompt_bundle(c, instruction))
    return bundles


def main():
    parser = argparse.ArgumentParser(description="Prepare or preview personalized cold outreach email drafts")
    parser.add_argument("--instruction", "-i", required=True, help="Custom directive/angle for the email (e.g. 'casual intro + ask if interested')")
    parser.add_argument("--target", "-t", help="Target specific creator name or ID")
    parser.add_argument("--limit", "-l", type=int, help="Limit number of prospects to process")
    parser.add_argument("--preview", action="store_true", help="Print prompt bundles without writing files")

    args = parser.parse_args()

    candidates = get_outreach_candidates(target=args.target, limit=args.limit)
    if not candidates:
        print("No eligible candidates found with verified emails.")
        print("Tip: Run 'uv run marketing captcha-queue' to add emails for remaining prospects.")
        return

    print(f"\n=== Found {len(candidates)} outreach candidate(s) with verified emails ===")
    for c in candidates:
        vid = f' | Video: "{c["video_title"][:30]}..."' if c.get("video_title") else ""
        print(f" • {c['title']} ({c['subscriber_count']:,} subs) ➔ {c['primary_email']}{vid}")

    print(f"\nUser Directive: \"{args.instruction}\"\n")

    if args.preview:
        bundles = prepare_candidate_bundles(args.instruction, target=args.target, limit=args.limit)
        print("--- Sample Prompt Bundle for AI ---")
        sample = bundles[0]
        print(f"Target: {sample['title']} <{sample['recipient_email']}>")
        print("\n[USER PROMPT]:")
        print(sample["user_prompt"])
        return

    print("👉 To have AI generate and save the drafts using this instruction, run the in-chat skill:")
    print(f'   /generate-emails "{args.instruction}"')
    print("Or specify a target:")
    print(f'   /generate-emails "{args.instruction}" for {candidates[0]["title"]}\n')


if __name__ == "__main__":
    main()
