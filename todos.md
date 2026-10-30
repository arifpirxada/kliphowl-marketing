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

## 🎯 Phase 2: YouTube API Integration & Enrichment (Current Priority)

- [ ] Build robust YouTube Data API v3 client (`src/discovery/yt_client.py`) with quota management & `.env` loader
- [ ] Test API key validity with a lightweight test call
- [ ] Build prospect enricher script (`src/enrichment/enrich_prospects.py`):
  - [ ] For prospects with video URLs (e.g. Caleb Writes Code, Cloud X Berry, Nova Designs), query `videos().list` to extract channel ID, channel title, and view count
  - [ ] For channels with `@handle` or channel ID, query `channels().list` to fetch exact subscriber count, video count, full description, and country
  - [ ] Update SQLite database (`data/marketing.db`) with enriched metadata
- [ ] Update `data/exports/prospects.csv` with fresh subscriber and channel counts

---

## 🔍 Phase 3: Email & Contact Scraping

- [ ] Build regex email extractor for channel descriptions (`src/enrichment/email_extractor.py`)
- [ ] Extract external links from channel metadata (Twitter/X, GitHub, personal websites, Substack)
- [ ] Build GitHub profile email finder for tech creators linking their GitHub repos
- [ ] Flag prospects requiring manual captcha check on YouTube's "View Email Address" page

---

## 🚀 Phase 4: Automated YouTube Prospect Discovery

- [ ] Implement search scraper using target query clusters (`system design animated`, `software architecture explained`, `how X works animation`, `visual guide to`)
- [ ] Filter candidates strictly by qualification criteria:
  - 5,000 to 250,000 subscribers (sweet spot)
  - Active within the last 60–90 days
  - English language tech topics
- [ ] Deduplicate candidates against existing records in `marketing.db`
- [ ] Batch import newly discovered qualified prospects into the database

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
