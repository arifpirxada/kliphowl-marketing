# KlipHowl Marketing & Prospecting Roadmap

This file tracks active milestones, backlog tasks, and completed items for the KlipHowl marketing and cold outreach engine.

---

## 📌 Phase 1: Storage & Initial Intake (Completed)

- [x] Create project documentation (`docs/PROJECT_OVERVIEW.md`, `docs/STORAGE_PLAN.md`, `docs/YOUTUBE_DISCOVERY_PLAN.md`, `docs/OUTREACH_STRATEGY.md`)
- [x] Design relational database schema (`data/schema.sql`) supporting YouTube & non-YouTube prospects, funnel states, and video samples
- [x] Initialize local SQLite database (`data/marketing.db`)
- [x] Create Markdown parser & sync utility (`src/storage/sync_prospects.py`)
- [x] Import initial 33 hand-curated prospects from `prospects.md` into `data/marketing.db`
- [x] Build CLI tool (`src/cli.py`) with `list`, `stats`, `import`, and `export` commands
- [x] Export snapshot to `data/exports/prospects.csv`
- [x] Configure `.gitignore` to protect `.env` and SQLite database

---

## 🎯 Phase 2: YouTube API Integration & Enrichment (Completed / Active)

- [x] Build robust YouTube Data API v3 client (`src/discovery/yt_client.py`) with quota management & `.env` loader
- [x] Test API key validity with a lightweight test call (1 unit used)
- [x] Build prospect enricher script (`src/enrichment/enrich_prospects.py` & `src/cli.py enrich`):
  - [x] For prospects with video URLs, queried `videos().list` in batch and extracted channel IDs, video titles, and view counts
  - [x] For channels with `@handle` or channel ID, queried `channels().list` in batch to fetch exact subscriber counts, video counts, full descriptions, and countries
  - [x] Updated SQLite database (`data/marketing.db`) with enriched metadata (32 channels updated)
- [x] Update `data/exports/prospects.csv` with fresh subscriber and channel counts

---

## 🔍 Phase 3: Email & Contact Scraping (ACTIVE - Human Captcha Queue)

- [x] Build regex email extractor for channel descriptions (`src/enrichment/email_extractor.py`)
- [x] Auto-discovered 6 verified business inquiry emails directly from channel descriptions:
  - Codist (`codiversitydev@gmail.com`)
  - Kai (`kaiexplains01102002@gmail.com`)
  - The AI Associate (`hello@theaiassociate.co`)
  - Brain Station Advanced (`videos.brainstation@gmail.com`)
  - The Coding Gopher (`thecodinggopher@gmail.com`)
  - Techs Explained (`alexjaxon614@gmail.com`)
- [x] Build secondary link crawler (`src/enrichment/link_crawler.py` & `src/enrichment/deep_enrich.py`):
  - Extracted Twitter/X, GitHub, and personal website links from descriptions
  - Crawled personal websites and found additional business emails:
    - VillageTalkies (`info@villagetalkies.com`)
    - Zeus / James HK (`james@jameshk.com`)
- [x] Build manual captcha queue CLI helper (`uv run marketing captcha-queue`):
  - Formats clean direct links to `@handle/about` for all channels missing an email
  - Added 1-command email setter (`uv run marketing set-email "<Channel Name>" <email>`)
- [ ] **In Progress by User:** Solve YouTube captchas on high-priority channels (e.g. *Caleb Writes Code*, *Cloud X Berry*, *Nova Designs*, *Tech With Diego*) and register their emails via `uv run marketing set-email`

---

## 🚀 Phase 4: Automated Prospect Discovery & Human Staging (Ready)

- [x] Configure discovery pipeline to **STAGING FIRST** (`data/discovery_staging.md`):
  - **Strict Rule:** Discovered candidates are NEVER inserted directly into `data/marketing.db`.
  - Staged into `data/discovery_staging.md` in Obsidian/GitHub callout format for human review.
  - The user reviews, deletes unwanted channels, and adjusts match ratings.
  - Merge into DB only upon running: `uv run marketing import-staging`.
- [x] Integrate CLI commands via `uv`:
  - `uv run discover`
  - `uv run marketing discover --query "..."`
  - `uv run marketing import-staging`
- [x] 16 newly discovered candidate channels staged in `data/discovery_staging.md` ready for user review.

---

## ✍️ Phase 5: Personalized Cold Outreach Generation (Next Priority)

---

## ✍️ Phase 5: Personalized Cold Outreach Generation

- [ ] Create personalization prompt template referencing specific video topics and diagram concepts
- [ ] Generate individualized markdown draft files in `outreach/drafts/{slug}.md` for top qualified prospects
- [ ] Include personalized hooks:
  - Mentioning a specific concept from their recent video
  - Highlighting time spent on manual diagramming (Excalidraw/Figma)
  - Offering a 15-second custom animated sample clip or free beta access
- [ ] Add CLI command to review and approve drafts (`python3 src/cli.py review`)

---

## 📬 Phase 6: Campaign Dispatch & Feedback Tracking

- [ ] Setup sending workflow (manual or SMTP dispatch via Brevo/Google Workspace)
- [ ] Log outreach dates and interaction events in `interaction_logs`
- [ ] Track response rate, positive replies, and creator feedback on KlipHowl's animation style
- [ ] Onboard interested creators to KlipHowl private beta
