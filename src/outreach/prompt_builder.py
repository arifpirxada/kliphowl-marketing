"""Context and Prompt Builder for AI-generated Personalized Cold Outreach Emails."""

from typing import Dict, Optional

from src.config import SENDER_NAME, PRODUCT_NAME, PRODUCT_DEMO_URL

KLIPHOWL_CORE_VALUE_PROP = """
- Product: KlipHowl (kliphowl.com)
- What it does: Converts a paragraph of a script or transcript section directly into a short, timed animated video clip (MP4).
- Aesthetic: Clean technical sketch aesthetic (Excalidraw / vector style diagrams, dynamic architectural flows, progressive step reveals).
- Workflow benefit: Tech explainers can drop the rendered MP4 directly into Premiere Pro, DaVinci Resolve, or Final Cut without spending 5–10 hours hand-drawing diagrams or animating keyframes.
"""

ANTI_SPAM_GUIDELINES = """
1. Be extremely concise (under 120 words).
2. Sound like a fellow engineer/builder reaching out, not a generic marketing agency.
3. NEVER use generic corporate filler ("I hope this email finds you well", "synergy", "disrupting", "game-changer").
4. CITE the specific video title or topic they recently published to prove genuine research.
5. Have ONE clear, low-friction call-to-action (e.g. "Would you be interested in a 30s sample clip or a free beta link to test on your next script?").
"""


def build_prospect_prompt_bundle(prospect: Dict, custom_instruction: str) -> Dict:
    """Combine prospect metadata, KlipHowl context, and user directive into a prompt bundle."""
    creator_title = prospect.get("title", "Creator")
    first_name = creator_title.split()[0] if " " in creator_title else creator_title
    handle = prospect.get("handle") or ""
    subs = prospect.get("subscriber_count", 0)
    subs_str = f"{subs / 1_000_000:.1f}M" if subs >= 1_000_000 else (f"{subs // 1_000}K" if subs >= 1_000 else str(subs))
    
    video_title = prospect.get("video_title") or "recent tech breakdown"
    sample_video_url = prospect.get("sample_video_url") or prospect.get("custom_url") or ""
    recipient_email = prospect.get("primary_email") or ""

    system_prompt = (
        "You are a cold outreach copywriting specialist writing to technical YouTube creators.\n"
        "Your goal is to craft a hyper-personalized, authentic cold email that creators actually reply to.\n\n"
        f"KlipHowl Value Proposition:\n{KLIPHOWL_CORE_VALUE_PROP}\n"
        f"Copywriting Rules:\n{ANTI_SPAM_GUIDELINES}\n"
    )

    user_prompt = f"""
Write a personalized cold email for this YouTube creator:

PROSPECT DETAILS:
- Channel: {creator_title} ({handle})
- Estimated First Name: {first_name}
- Subscriber Count: {subs_str} subscribers
- Recent Video Title: "{video_title}"
- Video URL: {sample_video_url}
- Recipient Email: {recipient_email}

SENDER INFO:
- Sender Name: {SENDER_NAME}
- Sender Role: Founder, {PRODUCT_NAME}

USER'S CUSTOM DIRECTIVE FOR THIS EMAIL:
"{custom_instruction}"

OUTPUT FORMAT REQUIRED:
Return ONLY the email in this exact markdown structure (no extra chatter):

### Subject:
<subject line>

### Body:
<body text>
"""

    return {
        "prospect_id": prospect["id"],
        "title": creator_title,
        "first_name": first_name,
        "recipient_email": recipient_email,
        "video_title": video_title,
        "sample_video_url": sample_video_url,
        "system_prompt": system_prompt.strip(),
        "user_prompt": user_prompt.strip(),
        "custom_instruction": custom_instruction
    }
