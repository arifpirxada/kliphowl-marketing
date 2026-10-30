#!/usr/bin/env python3
"""Command-Line Interface for KlipHowl Marketing & Prospect Intelligence."""

import argparse
import os
import sys

# Ensure marketing root is on python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.db import get_db, DEFAULT_DB_PATH
from src.storage.sync_prospects import import_prospects_to_db, export_prospects_to_csv
from src.enrichment.enrich_prospects import enrich_all_prospects
from src.enrichment.deep_enrich import run_deep_enrichment, get_captcha_queue
from src.discovery.search_prospects import discover_prospects
from src.storage.dedup import deduplicate_prospects

# ANSI Color Codes
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def format_match(match: str) -> str:
    m = (match or "").lower()
    if "very high" in m or "high" in m:
        return f"{GREEN}{match.upper():<9}{RESET}"
    elif "medium" in m:
        return f"{YELLOW}{match.capitalize():<9}{RESET}"
    elif "low" in m:
        return f"{RED}{match.capitalize():<9}{RESET}"
    return f"{match:<9}"


def format_number(val: int) -> str:
    if not val:
        return "-"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    elif val >= 1_000:
        return f"{val / 1_000:.0f}K"
    return str(val)


def cmd_import(args):
    # Check paths
    md_paths = [
        "data/prospects.md",
        "data/exports/prospects.md"
    ]
    target_path = None
    if args.file:
        target_path = args.file
    else:
        for p in md_paths:
            if os.path.exists(p):
                target_path = p
                break

    if not target_path or not os.path.exists(target_path):
        print(f"{RED}Error:{RESET} Could not find prospects.md in data/ or data/exports/")
        return

    print(f"Reading and syncing prospects from {CYAN}{target_path}{RESET}...")
    count = import_prospects_to_db(target_path, DEFAULT_DB_PATH)
    print(f"{GREEN}✓ Successfully imported / updated {count} prospects into {DEFAULT_DB_PATH}{RESET}")


def cmd_list(args):
    conn = get_db(DEFAULT_DB_PATH)
    cur = conn.cursor()

    query = "SELECT id, title, handle, subscriber_count, size_tier, match_level, prospect_type, primary_email, custom_url, sample_video_url, outreached FROM prospects"
    params = []

    if args.match:
        query += " WHERE LOWER(match_level) = LOWER(?)"
        params.append(args.match)

    query += " ORDER BY subscriber_count DESC, title ASC"
    if args.limit:
        query += f" LIMIT {args.limit}"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print(f"{YELLOW}No prospects found in database. Run 'python3 src/cli.py import' first!{RESET}")
        return

    print(f"\n{BOLD}{CYAN}=== KlipHowl Prospects Database ({len(rows)} records) ==={RESET}\n")
    print(f"{BOLD}{'Name / Title':<26} {'Match':<9} {'Subs':<7} {'Email':<25} {'Outreach':<10} {'Link / Sample'}{RESET}")
    print("-" * 110)

    for r in rows:
        title = r['title'][:24]
        match_str = format_match(r['match_level'])
        subs_str = format_number(r['subscriber_count'])
        email_str = (r['primary_email'] or '-')[:23]
        if r['primary_email']:
            email_str = f"{GREEN}{email_str:<23}{RESET}"
        else:
            email_str = f"{YELLOW}{email_str:<23}{RESET}"
            
        outreach_str = f"{GREEN}Sent{RESET}" if r['outreached'] else f"{YELLOW}No{RESET}"
        link = r['sample_video_url'] or r['custom_url'] or '-'
        if len(link) > 30:
            link = link[:27] + "..."

        print(f"{title:<26} {match_str} {subs_str:<7} {email_str} {outreach_str:<19} {link}")

    print("-" * 110)
    print(f"Total: {len(rows)} prospects | View detailed fields with SQLite or export with 'python3 src/cli.py export'\n")


def cmd_enrich(args):
    print(f"{CYAN}Enriching prospects with YouTube Data API v3 and scanning for emails...{RESET}")
    summary = enrich_all_prospects(DEFAULT_DB_PATH)
    print(f"\n{GREEN}✓ Enrichment completed!{RESET}")
    print(f"  • Channels updated: {summary['channels_updated']}")
    print(f"  • Business emails discovered: {summary['emails_found']}")
    print(f"  • YouTube API quota units consumed: {summary['quota_used']}")
    # Automatically export fresh CSV
    export_prospects_to_csv("data/exports/prospects.csv", DEFAULT_DB_PATH)
    print(f"  • Updated {CYAN}data/exports/prospects.csv{RESET}")


def cmd_stats(args):
    conn = get_db(DEFAULT_DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as total FROM prospects")
    total = cur.fetchone()['total']

    cur.execute("SELECT match_level, COUNT(*) as cnt FROM prospects GROUP BY match_level ORDER BY cnt DESC")
    matches = cur.fetchall()

    cur.execute("SELECT outreached, COUNT(*) as cnt FROM prospects GROUP BY outreached")
    outreach = cur.fetchall()

    conn.close()

    print(f"\n{BOLD}{CYAN}=== Prospect Pipeline Summary ==={RESET}")
    print(f"Total Prospects: {BOLD}{total}{RESET}\n")

    print(f"{BOLD}Breakdown by Match Level:{RESET}")
    for m in matches:
        lvl = m['match_level'] or 'unrated'
        print(f"  • {format_match(lvl)}: {m['cnt']}")

    print(f"\n{BOLD}Outreach Progress:{RESET}")
    for o in outreach:
        status_label = "Contacted" if o['outreached'] else "Not Contacted"
        print(f"  • {status_label}: {o['cnt']}")
    print()


def cmd_deep_enrich(args):
    print(f"{CYAN}Running deep enrichment: crawling websites, social links, and GitHub profiles...{RESET}")
    summary = run_deep_enrichment(DEFAULT_DB_PATH)
    print(f"\n{GREEN}✓ Deep enrichment complete!{RESET}")
    print(f"  • Social links updated: {summary['links_updated']}")
    print(f"  • Additional emails found: {summary['new_emails_found']}")
    print(f"  • Updated {CYAN}data/exports/prospects.csv{RESET}")


def cmd_captcha_queue(args):
    queue = get_captcha_queue(DEFAULT_DB_PATH)
    if not queue:
        print(f"{GREEN}All YouTube prospects already have emails!{RESET}")
        return

    print(f"\n{BOLD}{CYAN}=== Manual Email Captcha Queue ({len(queue)} channels missing email) ==={RESET}")
    print(f"YouTube gates some emails behind a web reCAPTCHA on their About page.")
    print(f"Open any of the links below, solve the captcha, then run:\n")
    print(f"  {BOLD}python3 src/cli.py set-email <prospect_title_or_id> <email>{RESET}\n")
    print(f"{BOLD}{'Name / Title':<26} {'Match':<9} {'Subs':<7} {'Direct About Link'}{RESET}")
    print("-" * 85)

    for item in queue:
        title = item["title"][:24]
        match_str = format_match(item["match"])
        subs_str = format_number(item["subs"])
        print(f"{title:<26} {match_str} {subs_str:<7} {item['about_url']}")

    print("-" * 85)


def cmd_set_email(args):
    conn = get_db(DEFAULT_DB_PATH)
    cur = conn.cursor()

    target = args.target.strip()
    email = args.email.strip()

    # Search by id or title
    cur.execute("""
        SELECT id, title, primary_email FROM prospects
        WHERE id = ? OR LOWER(title) = LOWER(?) OR title LIKE ?
    """, (target, target, f"%{target}%"))
    rows = cur.fetchall()

    if not rows:
        print(f"{RED}Error:{RESET} No prospect found matching '{target}'")
        conn.close()
        return

    prospect = rows[0]
    cur.execute("""
        UPDATE prospects
        SET primary_email = ?, email_source = 'manual', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (email, prospect["id"]))
    conn.commit()
    conn.close()

    export_prospects_to_csv("data/exports/prospects.csv", DEFAULT_DB_PATH)
    print(f"{GREEN}✓ Successfully set email for {BOLD}{prospect['title']}{RESET} ➔ {CYAN}{email}{RESET}")


def cmd_discover(args):
    queries = [args.query] if args.query else None
    print(f"{CYAN}Running automated YouTube prospect discovery...{RESET}")
    summary = discover_prospects(
        queries=queries,
        min_subs=args.min_subs,
        max_subs=args.max_subs,
        max_queries=args.queries,
        db_path=DEFAULT_DB_PATH
    )
    print(f"\n{GREEN}✓ Discovery completed!{RESET}")
    print(f"  • Queries run: {summary['queries_run']}")
    print(f"  • Channels scanned: {summary['channels_scanned']}")
    print(f"  • Newly qualified prospects added: {summary['qualified_added']}")
    print(f"  • Business emails discovered: {summary['emails_found']}")
    print(f"  • YouTube API quota units consumed: {summary['quota_used']}")
    print(f"  • Updated {CYAN}data/exports/prospects.csv{RESET}")


def cmd_dedup(args):
    print(f"{CYAN}Checking for duplicate channels by title and handle...{RESET}")
    count = deduplicate_prospects(DEFAULT_DB_PATH)
    print(f"{GREEN}✓ Deduplication completed! {count} duplicate records merged.{RESET}")


def cmd_export(args):
    out_csv = args.output or "data/exports/prospects.csv"
    count = export_prospects_to_csv(out_csv, DEFAULT_DB_PATH)
    print(f"{GREEN}✓ Exported {count} prospects to {CYAN}{out_csv}{RESET}")


def main():
    parser = argparse.ArgumentParser(description="KlipHowl Marketing & Prospect CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Import
    p_import = subparsers.add_parser("import", help="Import / sync prospects from markdown into SQLite")
    p_import.add_argument("--file", help="Path to markdown file (default: data/prospects.md or data/exports/prospects.md)")

    # List
    p_list = subparsers.add_parser("list", help="List prospects from SQLite database")
    p_list.add_argument("--match", help="Filter by match level (low, medium, high)")
    p_list.add_argument("--limit", type=int, help="Limit number of results")

    # Stats
    subparsers.add_parser("stats", help="Display aggregate stats of prospects")

    # Enrich
    subparsers.add_parser("enrich", help="Enrich prospects with YouTube API data and extract emails from descriptions")

    # Deep Enrich
    subparsers.add_parser("deep-enrich", help="Extract social links and crawl websites/GitHub for emails")

    # Captcha Queue
    subparsers.add_parser("captcha-queue", help="Display channels needing 1-click manual captcha check on YouTube")

    # Discover
    p_disc = subparsers.add_parser("discover", help="Automatically search & qualify new tech YouTube explainers")
    p_disc.add_argument("--query", help="Specific search query (optional)")
    p_disc.add_argument("--queries", type=int, default=2, help="Number of default queries to execute (default: 2)")
    p_disc.add_argument("--min-subs", type=int, default=5000, help="Minimum subscriber threshold (default: 5000)")
    p_disc.add_argument("--max-subs", type=int, default=350000, help="Maximum subscriber threshold (default: 350000)")

    # Set Email
    p_set = subparsers.add_parser("set-email", help="Manually set a verified email for a prospect")
    p_set.add_argument("target", help="Prospect title or ID")
    p_set.add_argument("email", help="Email address to assign")

    # Dedup
    subparsers.add_parser("dedup", help="Merge any duplicate channels by handle or title")

    # Export
    p_export = subparsers.add_parser("export", help="Export prospects from SQLite to CSV")
    p_export.add_argument("--output", help="Output CSV path (default: data/exports/prospects.csv)")

    args = parser.parse_args()
    if args.command == "import":
        cmd_import(args)
    elif args.command == "enrich":
        cmd_enrich(args)
    elif args.command == "deep-enrich":
        cmd_deep_enrich(args)
    elif args.command == "captcha-queue":
        cmd_captcha_queue(args)
    elif args.command == "discover":
        cmd_discover(args)
    elif args.command == "set-email":
        cmd_set_email(args)
    elif args.command == "dedup":
        cmd_dedup(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "export":
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
