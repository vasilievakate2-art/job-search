"""
config/settings.py
Central configuration – job search preferences (set your own values via .env)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (parent of config/).
# override=True so .env values replace any empty shell vars (e.g. ANTHROPIC_API_KEY= set by Claude Code env).
# In production (Railway), Railway injects real values at process start, so this is a no-op there.
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")       # kept for fallback; not used by default
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")    # Claude – resume tailoring & scoring
APIFY_API_TOKEN    = os.getenv("APIFY_API_TOKEN")
RAPIDAPI_KEY       = os.getenv("RAPIDAPI_KEY")
SLACK_BOT_TOKEN    = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID   = os.getenv("SLACK_CHANNEL_ID")
SECRET_KEY         = os.getenv("SECRET_KEY", "dev-secret-change-me")

# ── Scheduling ────────────────────────────────────────────────────────────────
DAILY_REPORT_HOUR      = int(os.getenv("DAILY_REPORT_HOUR", 10))   # 10 AM Pacific
SCRAPE_INTERVAL_HOURS  = int(os.getenv("SCRAPE_INTERVAL_HOURS", 2))

# ── Job Search Preferences ────────────────────────────────────────────────────
TARGET_TITLES = [
    "Content Lead",
    "Content Marketing Manager",
    "Marketing Manager",
    "Head of Marketing",
    "Brand Strategist",
    "Growth Marketer",
    "Social Media Manager",
    "Demand Generation Manager",
    "Field Marketing Manager",
    "Community Growth Manager",
    "Content Production Manager",
    "Marketing Content Manager",
    # Additional variations to widen the net
    "Senior Content Marketer",
    "VP of Marketing",
    "Director of Marketing",
    "Director of Content",
    "Content Strategy Manager",
    "Brand Marketing Manager",
    "Integrated Marketing Manager",
    "Senior Marketing Manager",
]

TARGET_LOCATIONS = [
    "San Francisco, CA",
    "San Jose, CA",
    "Sunnyvale, CA",
    "Mountain View, CA",
    "Santa Clara, CA",
    "Palo Alto, CA",
    "Oakland, CA",
    "Remote",
]

SALARY_MIN          = 110_000   # Absolute floor – remote roles; used for API params & hard filter
SALARY_MIN_ONSITE   = 120_000   # Floor for hybrid / on-site roles
SALARY_IDEAL        = 130_000   # Target salary for scoring purposes

MAX_POSTING_AGE_DAYS = 30   # Only jobs posted in the last 30 days

WORK_TYPES = ["hybrid", "remote", "on-site"]  # Acceptable work types

# Funding stages – only stable companies
FUNDING_STAGES = [
    "seed",
    "series_a",
    "series_b",
    "series_c",
    "public",
    "private",
]

# ── Applicant Info ────────────────────────────────────────────────────────────
# Set these in your .env file — they pre-fill application forms and personalise
# the resume tailoring prompts.
APPLICANT = {
    "name":             os.getenv("APPLICANT_NAME", "Your Name"),
    "email":            os.getenv("APPLICANT_EMAIL", "you@example.com"),
    "phone":            os.getenv("APPLICANT_PHONE", ""),
    "location":         os.getenv("APPLICANT_LOCATION", "San Francisco, CA"),
    "linkedin":         os.getenv("APPLICANT_LINKEDIN", ""),
    "portfolio":        os.getenv("APPLICANT_PORTFOLIO", ""),
    "work_auth":        os.getenv("WORK_AUTHORIZATION", "yes"),
    "needs_sponsorship": os.getenv("REQUIRES_SPONSORSHIP", "no"),
    "years_experience": os.getenv("YEARS_EXPERIENCE", "5+"),
    "desired_salary":   os.getenv("DESIRED_SALARY", "$120,000 – $150,000"),
    "start_date":       os.getenv("START_DATE", "Within 2–4 weeks"),
}

# ── File Paths ────────────────────────────────────────────────────────────────
BASE_DIR            = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_RESUME_PATH  = os.path.join(BASE_DIR, "data", os.getenv("RESUME_FILENAME", "resume.docx"))
RESUME_SUMMARY      = os.getenv("RESUME_SUMMARY", "")   # plain-text resume fallback for Railway
GENERATED_DIR       = os.path.join(BASE_DIR, "data", "generated_resumes")
LOGS_DIR            = os.path.join(BASE_DIR, "logs")
# On Railway, mount a Volume at /data so the DB survives redeploys.
# Locally it falls back to the repo's data/ folder.
_RAILWAY_DATA = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")   # set automatically when Volume is attached
DB_PATH = os.path.join(_RAILWAY_DATA, "jobs.db") if _RAILWAY_DATA else os.path.join(BASE_DIR, "data", "jobs.db")
