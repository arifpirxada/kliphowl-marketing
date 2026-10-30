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
    subparsers.add_parser("enrich", help="Enrich prospects with YouTube API data and extract emails")

    # Export
    p_export = subparsers.add_parser("export", help="Export prospects from SQLite to CSV")
    p_export.add_argument("--output", help="Output CSV path (default: data/exports/prospects.csv)")

    args = parser.parse_args()
    if args.command == "import":
        cmd_import(args)
    elif args.command == "enrich":
        cmd_enrich(args)
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
