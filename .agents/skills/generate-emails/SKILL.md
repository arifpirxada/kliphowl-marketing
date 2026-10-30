---
name: generate-emails
description: >-
  Generate personalized cold outreach email drafts for qualified KlipHowl prospects.
  Use this skill whenever the user asks to generate, write, or draft outreach emails,
  or uses a command like `/generate-emails "<custom instruction>"` or specifies a target like
  `generate email for Caleb Writes Code with instruction: "..."`.
---

# Generate Personalized Outreach Emails Skill

This skill guides the AI assistant in crafting tailored, high-converting cold outreach email drafts for tech YouTube explainers and educators who use diagrams and animations, based on live database metadata and user directives.

---

## 1. Trigger Scenarios

Activate this skill when the user:
- Types `/generate-emails "<directive>"`
- Asks to "generate emails for our prospects" or "draft an email for [Creator]"
- Provides a custom angle or pitch instruction for cold outreach

---

## 2. Procedure

### Step 1: Extract User Directives & Target
- Identify the user's custom instruction (e.g., *"Just introduce KlipHowl casually and ask if they are interested e.g. - Hey Caleb writes ... if you are interested I will send you the link..."*).
- Check if a specific prospect was targeted (e.g., `Caleb Writes Code`), or if the directive applies to all candidates with verified emails.

### Step 2: Fetch Prospect Context
Run a python snippet or call `get_outreach_candidates(target=target)`:
```bash
uv run python -c "
from src.outreach.repository import get_outreach_candidates
candidates = get_outreach_candidates(target='<Target or None>')
for c in candidates:
    print(c['title'], c['primary_email'], c['video_title'])
"
```
Or view candidates via CLI:
```bash
uv run draft-emails --instruction "<instruction>" --preview
```

### Step 3: Copywriting Guidelines
For each prospect:
1. **Subject Line:** Specific and conversational. Cite their video topic or channel name (e.g. *"Quick question on your [Topic] animation"* or *"Visual diagrams for [Channel Name]"*).
2. **Personalized Hook:** Reference their actual video title (from the `videos` table) and acknowledge their visual style (e.g. *"Loved your breakdown in '[Video Title]'..."*).
3. **Core Pitch:** Ground in KlipHowl's value proposition:
   - AI tool that converts a script/transcript section into a rendered animated diagram clip (MP4).
   - Clean tech sketch / Excalidraw aesthetic.
   - Saves 5–10 hours of manual diagram drawing/keyframing in video editors.
4. **Incorporate User's Custom Directive:** Closely adhere to the tone and call-to-action requested by the user.
5. **Length & Tone:** Strictly under 120 words. No sales clichés (*"I hope this email finds you well"*, *"synergy"*, *"game-changer"*).

### Step 4: Save Draft to Markdown & Database
Call the draft writer function to persist the email to `outreach/drafts/{slug}.md` and record it in `data/marketing.db`:

```python
from src.outreach.generator import write_draft_markdown

# prospect: Dict from get_outreach_candidates
write_draft_markdown(
    prospect=prospect,
    subject=subject_line,
    body=body_markdown,
    custom_instruction=user_instruction
)
```

### Step 5: Report to User
Provide clickable file links to the newly generated drafts in `outreach/drafts/` and remind the user they can review them in the terminal with:
```bash
uv run marketing review-drafts
```
