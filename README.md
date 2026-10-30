# KlipHowl Marketing & Prospecting Engine

Welcome to the **KlipHowl Marketing Workspace**. This directory hosts the prospect discovery, qualification, database, and personalized cold outreach pipeline for **KlipHowl**.

---

## 🚀 Quick Start with `uv`

This project uses **[`uv`](https://github.com/astral-sh/uv)** for fast, reliable Python package and environment management.

### Essential Commands

```bash
# 1. View all prospects in your terminal (subs, email, match level)
uv run marketing list

# 2. View pipeline summary statistics
uv run marketing stats

# 3. View the manual captcha queue (clickable About links for missing emails)
uv run marketing captcha-queue

# 4. Set a verified email after solving a YouTube captcha
uv run marketing set-email "Caleb Writes Code" caleb@example.com

# 5. Discover new prospects (NEVER writes to DB directly; stages to markdown for review)
uv run discover
# or: uv run marketing discover --query "system design animated"

# 6. Merge reviewed prospects from data/discovery_staging.md into the DB
uv run marketing import-staging

# 7. Sync manual edits from data/prospects.md into the DB
uv run marketing import

# 8. Preview or prepare AI outreach prompt bundles
uv run draft-emails --instruction "casual intro + ask if interested" --preview

# 9. Review prepared drafts
uv run marketing review-drafts

# 10. Export database to CSV
uv run marketing export
```

### In-Chat AI Email Drafting (`/generate-emails`)
Whenever you want AI to generate cold emails with a custom angle, simply type in chat:
```text
/generate-emails "Introduce KlipHowl casually, mention their recent video, and ask if they are interested."
```
Or for a specific creator:
```text
/generate-emails "Short 2-sentence intro and ask if they want a demo" for Caleb Writes Code
```

---

## 🎯 Target Audience

Our primary ICP (Ideal Customer Profile) is **Tech YouTube Explainers who use visual diagrams and animations** in their videos (e.g., System Design, Software Engineering, DevOps, Computer Science fundamentals, and Web Development channels).

These creators spend hours animating diagrams or hire motion designers. KlipHowl allows them to convert script/transcript excerpts directly into short animated clips (MP4) in seconds.

---

## 🛡️ Critical Workflow Rules

1. **Staging Before Database:**
   Whenever automated discovery runs, candidates are written to **`data/discovery_staging.md`**. They are **never added directly to `data/marketing.db`**.
   The human operator reviews the file, deletes unwanted channels, and runs `uv run marketing import-staging` to merge approved leads.
2. **Dual-Layer Review:**
   - Database source of truth: `data/marketing.db`
   - Human intake & notes: `data/prospects.md`
   - Staging for new leads: `data/discovery_staging.md`
   - Reviewable email drafts: `outreach/drafts/`

---

## 📂 Directory Layout

```text
marketing/
├── docs/                           # Architecture, plans, strategies (start here)
│   ├── PROJECT_OVERVIEW.md         # Full project background & ICP definition
│   ├── STORAGE_PLAN.md             # Database schema & prospect storage architecture
│   ├── YOUTUBE_DISCOVERY_PLAN.md   # YouTube Data API discovery & scraping pipeline
│   └── OUTREACH_STRATEGY.md        # Cold outreach copywriting & personalization guide
│
├── data/                           # Data storage (SQLite & CSV/JSON exports)
│   ├── marketing.db                # SQLite database (channels, videos, outreach)
│   ├── prospects.md                # Human-curated prospect tracker (Obsidian callout format)
│   ├── discovery_staging.md        # Staging area for newly discovered channels awaiting review
│   └── exports/                    # CSV / JSON exports
│       └── prospects.csv
│
├── outreach/                       # Cold email assets & campaign drafts
│   ├── templates/                  # Proven cold email copy templates
│   ├── drafts/                     # Generated personalized drafts per creator
│   └── sent/                       # Archive of dispatched messages
│
├── src/                            # Python automation code
│   ├── discovery/                  # YouTube API scraping & search scripts
│   ├── enrichment/                 # Channel qualification & email finders
│   ├── outreach/                   # Personalized copy generators
│   └── storage/                    # SQLite database models & query helpers
│
├── todos.md                        # Active project milestones & tasks
├── pyproject.toml                  # Python package configuration (managed via uv)
├── AGENTS.md                       # Operational rules for AI pair-programmers
└── README.md                       # This file
```
