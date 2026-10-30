# Guidelines for AI Agents Working in this Repository

This repository is dedicated to marketing, prospect intelligence, and personalized cold outreach for **KlipHowl**.

---

## 1. Product Context & Location

- The product being marketed is **KlipHowl**.
- Its codebase and documentation reside in the sibling directory:
  `../kliphowl` (`/home/arifpirxada/EMY/Code/Web_dev/current_projects/busi/ai-animation-maker/kliphowl`)
- **Key Reference:** Before formulating value propositions or feature claims, read:
  - `../kliphowl/AGENTS.md`
  - `../kliphowl/docs/ARCHITECTURE.md`
- KlipHowl converts transcript snippets and natural-language prompts into short animated video clips (MP4). It uses an AI scene planner (`@kliphowl/ai`) and an Excalimate/vector renderer (`@kliphowl/engine`) with animated step timelines.

---

## 2. Target Market

- **Target Persona:** Tech YouTube explainers and visual educators (System Design, Software Architecture, CS topics, Web Dev, DevOps, AI concepts).
- **Core Pain Point:** Tech explainers spend massive amounts of time drawing diagrams (Excalidraw, Figma, After Effects, Manim) or paying motion designers to make their videos engaging.
- **Value Proposition:** Turn transcript sections directly into animated clips in minutes, export to MP4, and drop them straight into video editing timelines (Premiere, DaVinci Resolve, Final Cut).

---

## 3. Data Architecture & Storage Rules

- **Source of Truth:** All prospects, channel metadata, video samples, and email drafts MUST be stored in the SQLite database at `data/marketing.db`.
- **CRITICAL DISCOVERY RULE (STAGING BEFORE DB):**
  - **Never add discovered channels directly into `data/marketing.db`!**
  - All automated discovery results MUST be staged into **`data/discovery_staging.md`** so the user can review them, discard poor matches, and edit scores.
  - Channels are ONLY imported into the database when the user triggers `uv run marketing import-staging` or explicitly requests it.
- **Reviewability:** For user convenience, generated email drafts should also be written or exported as markdown files into `outreach/drafts/` so the user can easily inspect, tweak, and approve them before sending.
- Read **[`docs/STORAGE_PLAN.md`](docs/STORAGE_PLAN.md)** before designing or modifying database tables or schemas.
- Do NOT delete existing prospect records or outreach history without explicit user instruction.

---

## 4. Code Standards & Environment

- **Python Environment Manager:** Always use **`uv`** for dependency management and command execution (`uv run marketing ...`, `uv run discover ...`).
- **Dependencies:** Keep external dependencies minimal. Use `uv add` when introducing required libraries.
- **API Credentials:** Never hardcode YouTube API keys or credentials in code. Store them in `.env` (gitignored) and load with `os.environ` via `src/config.py`.

---

## 5. Documentation First

- If you make structural changes to data models, prospecting workflows, or discovery logic, update the corresponding documentation files in `docs/` immediately.
- Maintain consistency across `PROJECT_OVERVIEW.md`, `STORAGE_PLAN.md`, `YOUTUBE_DISCOVERY_PLAN.md`, and `OUTREACH_STRATEGY.md`.
