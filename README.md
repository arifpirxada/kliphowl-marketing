# KlipHowl Marketing & Prospecting Engine

Welcome to the **KlipHowl Marketing Workspace**. This directory hosts the prospect discovery, qualification, database, and personalized cold outreach pipeline for **KlipHowl**.

---

## 🚀 Quick Navigation for Agents & Humans

Before executing commands or writing scripts, review the primary documentation in `docs/`:

1. **[`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md)** — What KlipHowl is, the product architecture, value proposition, target market (Tech YouTube Explainers), and project objectives.
2. **[`docs/STORAGE_PLAN.md`](docs/STORAGE_PLAN.md)** — Source-of-truth data architecture: SQLite database schema (`data/marketing.db`), prospect storage, outreach drafts, and file layout.
3. **[`docs/YOUTUBE_DISCOVERY_PLAN.md`](docs/YOUTUBE_DISCOVERY_PLAN.md)** — YouTube Data API v3 prospecting strategy, search keywords, qualification criteria, and email extraction workflows.
4. **[`docs/OUTREACH_STRATEGY.md`](docs/OUTREACH_STRATEGY.md)** — Email templates, personalization frameworks, value hooks, and follow-up cadences.

---

## 🎯 Target Audience

Our primary ICP (Ideal Customer Profile) is **Tech YouTube Explainers who use visual diagrams and animations** in their videos (e.g., System Design, Software Engineering, DevOps, Computer Science fundamentals, and Web Development channels).

These creators spend hours animating diagrams or hire motion designers. KlipHowl allows them to convert script/transcript excerpts directly into short animated clips (MP4) in seconds.

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
│   └── exports/                    # CSV / JSON exports for quick review
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
├── AGENTS.md                       # Operational rules for AI pair-programmers
└── README.md                       # This file
```

---

## 🛠️ Stack & Conventions

- **Language:** Python 3.10+ (Current environment: Python 3.14).
- **Primary Data Store:** SQLite (`data/marketing.db`) — zero external infrastructure, relational integrity, portable.
- **External APIs:** YouTube Data API v3 (search, channels, videos, playlists).
- **Product Reference:** Located at `../kliphowl` (`docs/ARCHITECTURE.md`).
