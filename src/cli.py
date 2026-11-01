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
from src.discovery.search_prospects import discover_prospects_to_staging, DEFAULT_STAGING_PATH
from src.storage.dedup import deduplicate_prospects
from src.outreach.repository import (
    get_all_drafts,
    get_outreach_candidates,
    get_draft_by_id,
    get_draft_by_target,
    update_draft_status,
    approve_all_ready_drafts,
    sync_drafts_from_disk,
    record_prospect_reply
)
from src.config import ADMIN_EMAIL
from src.outreach.generator import prepare_candidate_bundles
from src.outreach.sender import (
    test_smtp_connection,
    dispatch_draft,
    dispatch_all_approved,
    send_test_draft_to_admin,
    send_admin_notification
)

# ANSI Color Codes
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def cmd_help_overview(args=None):
    """Display a grouped, colorful, intuitive workflow cheatsheet for KlipHowl Marketing."""
    print(f"""
{BOLD}{CYAN}===================================================================================================={RESET}
                        {BOLD}🚀 KLIPHOWL MARKETING WORKFLOW & COMMAND CHEATSHEET{RESET}
{BOLD}{CYAN}===================================================================================================={RESET}

{BOLD}{MAGENTA}1. 🎯 PROSPECT MANAGEMENT & CAPTCHAS{RESET}
   {CYAN}uv run marketing list{RESET}
       List all prospects (subs, verified business emails, match score, links).
   {CYAN}uv run marketing stats{RESET}
       Show total prospects, breakdown by match level, and outreach progress.
   {CYAN}uv run marketing captcha-queue{RESET}
       Show channels needing 1-click manual captcha check with direct YouTube About URLs.
   {CYAN}uv run marketing set-email "<Channel Name>" <email>{RESET}
       Save a verified email for any channel (updates DB and re-exports CSV).

{BOLD}{MAGENTA}2. 🔍 AUTOMATED DISCOVERY & HUMAN REVIEW (STAGING FIRST){RESET}
   {CYAN}uv run discover{RESET}  {YELLOW}(or: uv run marketing discover){RESET}
       Search YouTube for tech explainers & stage candidate channels into {CYAN}data/discovery_staging.md{RESET}.
       {BOLD}Note:{RESET} Discovery NEVER pollutes the DB directly!
   {CYAN}uv run discover --query "microservices architecture visual guide"{RESET}
       Search a specific custom topic.
   👉 {BOLD}Action:{RESET} Open {CYAN}data/discovery_staging.md{RESET}, delete channels you dislike, adjust match ratings.
   {CYAN}uv run marketing import-staging{RESET}
       Merge your approved prospects from {CYAN}data/discovery_staging.md{RESET} into SQLite DB.
   {CYAN}uv run marketing dedup{RESET}
       Safely merge duplicate channels by handle or title without data loss.

{BOLD}{MAGENTA}3. ✍️ PERSONALIZED COLD EMAIL DRAFTING, EDITING & REVIEW{RESET}
   {BOLD}In-Chat AI Command:{RESET}
       {GREEN}/generate-emails "<your custom directive>"{RESET}
       AI reads prospect metadata + specific video titles and writes drafts into {CYAN}outreach/drafts/{{slug}}.md{RESET}.
       Example: {GREEN}/generate-emails "Casual intro, ask if they want a 15s demo" for Caleb Writes Code{RESET}
   {BOLD}✏️ Human Editing & Personalization:{RESET}
       Open and edit any file in {CYAN}outreach/drafts/{{slug}}.md{RESET} directly in your editor.
       Any changes you make to Subject or Body {GREEN}automatically sync{RESET} to SQLite when reviewing or sending!
   {CYAN}uv run marketing sync-drafts{RESET}
       Explicitly re-sync markdown file edits into SQLite.
   {CYAN}uv run draft-emails -i "<prompt>" --preview{RESET}
       Preview AI prompt bundles for creators in terminal without writing files.
   {CYAN}uv run marketing review{RESET}
       View table of all email drafts and their current review status.
   {CYAN}uv run marketing review --id <ID>{RESET}  {YELLOW}(or: --target "<Name>"){RESET}
       Inspect full subject and body with interactive [{BOLD}A{RESET}]pprove / [{BOLD}R{RESET}]eject / [{BOLD}S{RESET}]kip prompt.
   {CYAN}uv run marketing review --approve <ID | all>{RESET}
       Approve draft(s) for sending (only approved drafts can ever be dispatched).

{BOLD}{MAGENTA}4. 📬 BREVO SMTP TESTING & DISPATCH{RESET}
   {CYAN}uv run marketing test-email{RESET}
       Verify Brevo SMTP connection & credentials ({CYAN}smtp-relay.brevo.com:587{RESET}).
   {CYAN}uv run marketing test-email --draft <name | ID>{RESET}  {YELLOW}(or: test-mail --draft <name>){RESET}
       Send a test preview of any draft directly to {CYAN}ADMIN_EMAIL{RESET} to inspect it in your inbox!
   {CYAN}uv run marketing send-approved --dry-run{RESET}
       Safety simulation: prints what would be sent without delivering actual emails.
   {CYAN}uv run marketing send-approved{RESET}
       Dispatch all approved drafts live (with built-in safety pacing delay).
       A confirmation summary report is automatically delivered to {CYAN}ADMIN_EMAIL{RESET}.
       Sent copies are archived in {CYAN}outreach/sent/YYYY-MM/{RESET}.
   {CYAN}uv run marketing send --id <ID>{RESET}
       Dispatch a single approved draft by its database ID.

{BOLD}{MAGENTA}5. 📊 OUTREACH TRACKING & RESPONSE LOGGING{RESET}
   {CYAN}uv run marketing stats{RESET}
       View funnel metrics (discovered, in_outreach, responded, customers).
   {CYAN}uv run marketing log-reply "<Channel Name>" --status <interested|not_interested|ghosted>{RESET}
       Record creator reply, optional notes, or conversion ({CYAN}--signed-up{RESET}).
       Updates SQLite outreach status and refreshes {CYAN}data/exports/prospects.csv{RESET}.

{BOLD}{MAGENTA}6. 💾 DATA SYNC & SPREADSHEET EXPORTS{RESET}
   {CYAN}uv run marketing export{RESET}
       Export entire database to {CYAN}data/exports/prospects.csv{RESET} for Excel/Sheets.
   {CYAN}uv run marketing import{RESET}
       Sync manual additions from {CYAN}data/prospects.md{RESET} into SQLite DB.

{BOLD}{CYAN}===================================================================================================={RESET}
""")


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

    cur.execute("SELECT response_status, COUNT(*) as cnt FROM prospects WHERE response_status != 'none' GROUP BY response_status")
    responses = cur.fetchall()

    cur.execute("SELECT COUNT(*) as cnt FROM prospects WHERE signed_up = 1")
    signed = cur.fetchone()["cnt"]

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

    if responses:
        print(f"\n{BOLD}Responses Recorded:{RESET}")
        for r in responses:
            print(f"  • {r['response_status'].capitalize()}: {r['cnt']}")

    if signed > 0:
        print(f"\n{BOLD}{GREEN}🎉 Active Customers / Signups:{RESET} {signed}")
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
    print(f"  {BOLD}uv run marketing set-email \"<Channel Name>\" <email>{RESET}\n")
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
    staging_path = args.output or DEFAULT_STAGING_PATH
    print(f"{CYAN}Running YouTube discovery (candidates will be staged to {staging_path})...{RESET}")
    summary = discover_prospects_to_staging(
        queries=queries,
        min_subs=args.min_subs,
        max_subs=args.max_subs,
        max_queries=args.queries,
        output_path=staging_path,
        db_path=DEFAULT_DB_PATH
    )
    print(f"\n{GREEN}✓ Discovery complete! Staged for human review:{RESET}")
    print(f"  • Queries run: {summary['queries_run']}")
    print(f"  • Channels scanned: {summary['channels_scanned']}")
    print(f"  • Staged in markdown: {summary['qualified_staged']}")
    print(f"  • Business emails discovered: {summary['emails_found']}")
    print(f"  • YouTube API quota units consumed: {summary['quota_used']}")
    print(f"\n{BOLD}👉 Review candidate channels in:{RESET} {CYAN}{summary['output_path']}{RESET}")
    print(f"   Delete any you don't want, adjust match ratings, then run:")
    print(f"   {BOLD}uv run marketing import-staging{RESET}\n")


def cmd_import_staging(args):
    staging_path = args.file or DEFAULT_STAGING_PATH
    if not os.path.exists(staging_path):
        print(f"{RED}Error:{RESET} Staging file not found: {staging_path}")
        return

    print(f"{CYAN}Importing reviewed prospects from {staging_path} into database...{RESET}")
    count = import_prospects_to_db(staging_path, DEFAULT_DB_PATH)
    dedup_count = deduplicate_prospects(DEFAULT_DB_PATH)
    export_prospects_to_csv("data/exports/prospects.csv", DEFAULT_DB_PATH)

    print(f"{GREEN}✓ Successfully merged {count} reviewed prospects into database!{RESET}")
    if dedup_count > 0:
        print(f"  • Merged {dedup_count} duplicates.")
    print(f"  • Updated {CYAN}data/exports/prospects.csv{RESET}")


def cmd_dedup(args):
    print(f"{CYAN}Checking for duplicate channels by title and handle...{RESET}")
    count = deduplicate_prospects(DEFAULT_DB_PATH)
    print(f"{GREEN}✓ Deduplication completed! {count} duplicate records merged.{RESET}")


def cmd_review(args):
    # Case 1: Direct approve
    if args.approve:
        target = args.approve.strip()
        if target.lower() == "all":
            cnt = approve_all_ready_drafts(DEFAULT_DB_PATH)
            print(f"{GREEN}✓ Approved all {cnt} ready drafts!{RESET}")
        elif target.isdigit():
            draft_id = int(target)
            if update_draft_status(draft_id, "approved"):
                d = get_draft_by_id(draft_id)
                name = d['channel_title'] if d else target
                print(f"{GREEN}✓ Draft #{draft_id} for '{name}' is now APPROVED for sending!{RESET}")
            else:
                print(f"{RED}Error:{RESET} Draft #{draft_id} not found.")
        else:
            d = get_draft_by_target(target)
            if d and update_draft_status(d["id"], "approved"):
                print(f"{GREEN}✓ Draft #{d['id']} for '{d['channel_title']}' is now APPROVED for sending!{RESET}")
            else:
                print(f"{RED}Error:{RESET} No draft found matching '{target}'.")
        return

    # Case 2: Direct reject
    if args.reject:
        target = args.reject.strip()
        draft_id = int(target) if target.isdigit() else None
        d = get_draft_by_id(draft_id) if draft_id else get_draft_by_target(target)
        if d and update_draft_status(d["id"], "rejected"):
            print(f"{YELLOW}✓ Draft #{d['id']} for '{d['channel_title']}' marked as REJECTED.{RESET}")
        else:
            print(f"{RED}Error:{RESET} Draft not found matching '{target}'.")
        return

    # Case 3: Inspect single draft
    if args.id or args.target:
        d = get_draft_by_id(args.id) if args.id else get_draft_by_target(args.target)
        if not d:
            print(f"{RED}Error:{RESET} Draft not found.")
            return

        print(f"\n{BOLD}{CYAN}=== Reviewing Draft #{d['id']}: {d['channel_title']} ==={RESET}")
        print(f"Status: {d['status']} | To: {d['recipient_email']}")
        print(f"Draft File: {d['draft_file_path']}")
        print("-" * 65)
        print(f"{BOLD}Subject:{RESET} {d['subject_line']}\n")
        print(d["body_markdown"])
        print("-" * 65)

        try:
            choice = input(f"Action: [{BOLD}A{RESET}]pprove / [{BOLD}R{RESET}]eject / [{BOLD}S{RESET}]kip? ").strip().lower()
            if choice == "a":
                update_draft_status(d["id"], "approved")
                print(f"{GREEN}✓ Draft #{d['id']} approved!{RESET}")
            elif choice == "r":
                update_draft_status(d["id"], "rejected")
                print(f"{YELLOW}✓ Draft #{d['id']} rejected.{RESET}")
            else:
                print("Skipped.")
        except (EOFError, KeyboardInterrupt):
            print()
        return

    # Case 4: Default list
    drafts = get_all_drafts(DEFAULT_DB_PATH)
    if not drafts:
        print(f"\n{YELLOW}No email drafts found in database.{RESET}")
        print("To generate drafts with AI, run:")
        print('  /generate-emails "<your instruction here>"')
        print("Or preview prompt bundles via CLI:")
        print('  uv run draft-emails --instruction "<instruction>" --preview\n')
        return

    print(f"\n{BOLD}{CYAN}=== Outreach Email Drafts Review ({len(drafts)} records) ==={RESET}\n")
    print(f"{BOLD}{'ID':<4} {'Channel Title':<22} {'Status':<18} {'Recipient Email':<28} {'Subject'}{RESET}")
    print("-" * 105)

    for d in drafts:
        status_color = GREEN if d["status"] == "approved" else (CYAN if d["status"] == "ready_for_review" else (YELLOW if d["status"] == "sent" else RED))
        status_str = f"{status_color}{d['status']:<18}{RESET}"
        subj = (d["subject_line"] or "")[:30]
        print(f"{d['id']:<4} {d['channel_title'][:20]:<22} {status_str} {d['recipient_email']:<28} {subj}")

    print("-" * 105)
    print("Commands:")
    print("  • Inspect draft details:  uv run marketing review --id <ID>")
    print("  • Approve draft:          uv run marketing review --approve <ID | all>")
    print("  • Reject draft:           uv run marketing review --reject <ID>")
    print("  • Dispatch approved:      uv run marketing send-approved\n")


def cmd_test_email(args):
    draft_arg = getattr(args, "draft", None)
    if draft_arg:
        if not ADMIN_EMAIL:
            print(f"{RED}Error:{RESET} ADMIN_EMAIL is not set in .env.")
            print("Please add ADMIN_EMAIL=your_email@domain.com in .env to receive test drafts.")
            return

        draft = None
        if str(draft_arg).isdigit():
            draft = get_draft_by_id(int(draft_arg))
        if not draft:
            draft = get_draft_by_target(draft_arg)

        if not draft:
            print(f"{RED}Error:{RESET} Could not find any draft matching '{draft_arg}'.")
            print("Run 'uv run marketing review' to see available draft IDs and channels.")
            return

        print(f"{CYAN}Sending test preview of draft #{draft['id']} ({draft['channel_title']}) to ADMIN_EMAIL ({ADMIN_EMAIL})...{RESET}")
        try:
            send_test_draft_to_admin(draft)
            print(f"{GREEN}✓ SUCCESS: Test preview delivered to {ADMIN_EMAIL}!{RESET}")
            print(f"  • Target Creator : {draft['channel_title']}")
            print(f"  • Real Recipient : {draft['recipient_email']}")
            print(f"  • Subject        : {draft['subject_line']}")
            print(f"  • Status in DB   : {draft['status']} (unchanged)")
        except Exception as e:
            print(f"{RED}✗ ERROR: Failed to send test preview:{RESET} {e}")
        return

    print(f"{CYAN}Testing Brevo SMTP connection and authentication...{RESET}")
    try:
        if test_smtp_connection():
            print(f"{GREEN}✓ SUCCESS: Authenticated with Brevo SMTP successfully! Ready for outreach dispatch.{RESET}")
            if ADMIN_EMAIL:
                print(f"  • ADMIN_EMAIL configured: {CYAN}{ADMIN_EMAIL}{RESET}")
                print(f"  • To send a test draft preview to your inbox, run:")
                print(f"    {BOLD}uv run marketing test-email --draft <draft_name or ID>{RESET}")
    except Exception as e:
        print(f"{RED}✗ ERROR: SMTP Connection failed:{RESET} {e}")


def cmd_send(args):
    if args.id:
        try:
            res = dispatch_draft(args.id, dry_run=args.dry_run, db_path=DEFAULT_DB_PATH)
            if res.get("dry_run"):
                print(f"{YELLOW}[DRY RUN] Would send draft #{args.id} to {res['recipient']}{RESET}")
            else:
                print(f"{GREEN}✓ Successfully dispatched email #{args.id} to {res['recipient']}!{RESET}")
                print(f"  • Archived copy saved to: {CYAN}{res.get('archive_path')}{RESET}")
                if ADMIN_EMAIL:
                    from datetime import datetime
                    send_admin_notification(
                        subject=f"[KlipHowl Outreach] Single Email Sent: Draft #{args.id}",
                        body_text=f"Outreach email #{args.id} was dispatched to {res['recipient']} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.\n\nArchived copy: {res.get('archive_path')}"
                    )
        except Exception as e:
            print(f"{RED}Error:{RESET} {e}")
    else:
        print(f"{CYAN}Dispatching approved outreach drafts (dry_run={args.dry_run})...{RESET}")
        res = dispatch_all_approved(limit=args.limit, dry_run=args.dry_run, db_path=DEFAULT_DB_PATH)
        print(f"\n{BOLD}{CYAN}=== Outreach Dispatch Summary ==={RESET}")
        print(f"  • Total Approved: {res['total_approved']}")
        print(f"  • Sent: {res['sent_count']}")
        print(f"  • Dry Run: {res['dry_run']}")
        if res.get("results"):
            for r in res["results"]:
                status = f"{GREEN}Sent{RESET}" if r.get("sent") else (f"{YELLOW}Dry Run{RESET}" if r.get("dry_run") else f"{RED}Failed: {r.get('error')}{RESET}")
                print(f"   • Draft #{r['draft_id']}: {status}")


def cmd_sync_drafts(args):
    """Scan outreach/drafts/*.md for manual edits and sync to SQLite."""
    print(f"{CYAN}Scanning outreach/drafts/*.md for manual edits...{RESET}")
    cnt = sync_drafts_from_disk(db_path=DEFAULT_DB_PATH)
    if cnt > 0:
        print(f"{GREEN}✓ Synchronized {cnt} edited draft(s) into database!{RESET}")
    else:
        print("✓ All drafts are up-to-date with database.")


def cmd_log_reply(args):
    """Record creator reply or conversion into DB and refresh CSV."""
    res = record_prospect_reply(
        target=args.target,
        response_status=args.status,
        notes=args.notes,
        signed_up=args.signed_up,
        free_credits=args.free_credits or 0,
        db_path=DEFAULT_DB_PATH
    )
    if not res:
        print(f"{RED}Error:{RESET} Prospect matching '{args.target}' not found.")
        return
    print(f"{GREEN}✓ Logged response for '{res['title']}':{RESET}")
    print(f"  • Response Status: {BOLD}{res['response_status']}{RESET}")
    print(f"  • Overall Prospect Status: {BOLD}{res['status']}{RESET}")
    if args.signed_up:
        print(f"  • Signed Up: {GREEN}Yes 🎉{RESET}")
    if args.notes:
        print(f"  • Notes: {args.notes}")
    print(f"  • Updated CSV export at {CYAN}data/exports/prospects.csv{RESET}")


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
    p_disc.add_argument("--output", help="Path to write staging file (default: data/discovery_staging.md)")

    # Set Email
    p_set = subparsers.add_parser("set-email", help="Manually set a verified email for a prospect")
    p_set.add_argument("target", help="Prospect title or ID")
    p_set.add_argument("email", help="Email address to assign")

    # Import Staging
    p_imp_stg = subparsers.add_parser("import-staging", help="Merge reviewed prospects from data/discovery_staging.md into SQLite")
    p_imp_stg.add_argument("--file", help="Path to staging file (default: data/discovery_staging.md)")

    # Dedup
    subparsers.add_parser("dedup", help="Merge any duplicate channels by handle or title")

    # Review Drafts
    p_rev = subparsers.add_parser("review", help="Review and approve cold outreach email drafts")
    p_rev.add_argument("--id", type=int, help="Inspect a specific draft by ID")
    p_rev.add_argument("--target", help="Inspect draft for specific creator")
    p_rev.add_argument("--approve", help="Approve draft by ID, creator name, or 'all'")
    p_rev.add_argument("--reject", help="Reject draft by ID or creator name")

    # Legacy alias review-drafts
    subparsers.add_parser("review-drafts", help="Alias for review")

    # Draft Emails
    p_draft = subparsers.add_parser("draft-emails", help="Prepare prompt bundles or generate personalized outreach drafts")
    p_draft.add_argument("--instruction", "-i", required=True, help="Custom directive/angle for the email")
    p_draft.add_argument("--target", "-t", help="Target specific creator name or ID")
    p_draft.add_argument("--limit", "-l", type=int, help="Limit number of prospects to process")
    p_draft.add_argument("--preview", action="store_true", help="Print prompt bundles without writing files")

    # Test Email Connection & Preview
    p_test = subparsers.add_parser("test-email", help="Verify Brevo SMTP connectivity or send test draft to ADMIN_EMAIL")
    p_test.add_argument("subaction", nargs="?", help="Optional subcommand (e.g. 'mail')")
    p_test.add_argument("--draft", help="Draft ID or channel name to preview in ADMIN_EMAIL inbox")

    p_test_m = subparsers.add_parser("test-mail", help="Alias for test-email")
    p_test_m.add_argument("subaction", nargs="?", help="Optional subcommand")
    p_test_m.add_argument("--draft", help="Draft ID or channel name to preview in ADMIN_EMAIL inbox")

    p_test_short = subparsers.add_parser("test", help="Alias for test-email")
    p_test_short.add_argument("subaction", nargs="?", help="Optional subcommand (e.g. 'mail')")
    p_test_short.add_argument("--draft", help="Draft ID or channel name to preview in ADMIN_EMAIL inbox")

    # Send Emails
    p_send = subparsers.add_parser("send", help="Dispatch approved outreach email(s) via Brevo SMTP")
    p_send.add_argument("--id", type=int, help="Send a specific approved draft ID")
    p_send.add_argument("--limit", type=int, default=20, help="Maximum emails to send in batch (default: 20)")
    p_send.add_argument("--dry-run", action="store_true", help="Simulate sending without actually delivering")

    # Send Approved Alias
    p_send_app = subparsers.add_parser("send-approved", help="Dispatch all approved drafts via Brevo SMTP")
    p_send_app.add_argument("--limit", type=int, default=20, help="Maximum emails to send in batch (default: 20)")
    p_send_app.add_argument("--dry-run", action="store_true", help="Simulate sending without actually delivering")

    # Export
    p_export = subparsers.add_parser("export", help="Export prospects from SQLite to CSV")
    p_export.add_argument("--output", help="Output CSV path (default: data/exports/prospects.csv)")

    # Sync Drafts
    subparsers.add_parser("sync-drafts", help="Scan outreach/drafts/*.md and sync manual edits into SQLite")

    # Log Reply
    p_log = subparsers.add_parser("log-reply", help="Log creator reply or conversion into DB")
    p_log.add_argument("target", help="Prospect channel name, handle, or ID")
    p_log.add_argument("--status", choices=["interested", "not_interested", "ghosted", "none"], required=True, help="Response status")
    p_log.add_argument("--notes", help="Notes on reply or feedback")
    p_log.add_argument("--signed-up", action="store_true", help="Mark prospect as signed up user")
    p_log.add_argument("--free-credits", type=int, default=0, help="Number of free credits allocated")

    # Workflow Help Cheatsheet
    subparsers.add_parser("help", help="Show complete workflow cheatsheet")

    if len(sys.argv) == 1:
        cmd_help_overview()
        return

    args = parser.parse_args()
    if args.command == "help":
        cmd_help_overview()
    elif args.command == "import":
        cmd_import(args)
    elif args.command == "enrich":
        cmd_enrich(args)
    elif args.command == "deep-enrich":
        cmd_deep_enrich(args)
    elif args.command == "captcha-queue":
        cmd_captcha_queue(args)
    elif args.command == "discover":
        cmd_discover(args)
    elif args.command == "import-staging":
        cmd_import_staging(args)
    elif args.command == "set-email":
        cmd_set_email(args)
    elif args.command == "dedup":
        cmd_dedup(args)
    elif args.command in ("review", "review-drafts"):
        # Ensure default attributes exist if called via alias
        if not hasattr(args, "id"):
            args.id = None
        if not hasattr(args, "target"):
            args.target = None
        if not hasattr(args, "approve"):
            args.approve = None
        if not hasattr(args, "reject"):
            args.reject = None
        cmd_review(args)
    elif args.command == "draft-emails":
        from src.outreach.generator import main as gen_main
        gen_main()
    elif args.command in ("test-email", "test-mail", "test"):
        cmd_test_email(args)
    elif args.command in ("send", "send-approved"):
        if not hasattr(args, "id"):
            args.id = None
        cmd_send(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "sync-drafts":
        cmd_sync_drafts(args)
    elif args.command == "log-reply":
        cmd_log_reply(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
