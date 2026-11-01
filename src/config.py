"""Configuration and environment variables loader."""

import os
from typing import Optional

MARKETING_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(MARKETING_ROOT, ".env")


def load_env_file(path: str = ENV_PATH) -> dict:
    """Parse .env file into a dictionary without external dependencies."""
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                env[k] = v
                if k not in os.environ:
                    os.environ[k] = v
    return env


# Automatically load on import
_env = load_env_file()

YOUTUBE_API_KEY: Optional[str] = os.getenv("YOUTUBE_API_KEY")
GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", os.path.join(MARKETING_ROOT, "data", "marketing.db"))
ADMIN_EMAIL: Optional[str] = os.getenv("ADMIN_EMAIL")
SENDER_NAME: str = os.getenv("SENDER_NAME", "Arif")
SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "outreach@kliphowl.com")
PRODUCT_NAME: str = os.getenv("PRODUCT_NAME", "KlipHowl")
PRODUCT_DEMO_URL: str = os.getenv("PRODUCT_DEMO_URL", "https://kliphowl.com")

# Brevo SMTP Configuration
BREVO_SMTP_HOST: str = os.getenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
BREVO_SMTP_PORT: int = int(os.getenv("BREVO_SMTP_PORT", "587"))
BREVO_SMTP_LOGIN: Optional[str] = os.getenv("BREVO_SMTP_LOGIN")
BREVO_SMTP_KEY: Optional[str] = os.getenv("BREVO_SMTP_KEY")
EMAIL_FROM: str = os.getenv("EMAIL_FROM", SENDER_EMAIL)
