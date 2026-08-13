"""
Shared configuration for the daily learning pipeline.

Every tunable that affects cost or reading time lives here, so you can dial
the brief up or down without touching prompt code.
"""

import os
from datetime import date

from dotenv import load_dotenv

# Local runs read .env; in Actions the same names arrive as real env vars and
# this is a no-op. config is imported first by every stage, so loading here
# means no stage has to remember to do it.
load_dotenv()

MODEL = "claude-sonnet-5"

# Volume knobs. These drive both the prompts and the API bill: each research
# stage is one Claude call that runs ~8-12 server-side web searches, billed
# at $10/1000 searches on top of tokens. Halving these roughly halves the
# monthly cost.
ITEMS_PER_RESEARCH_STAGE = 6   # x2 stages = 12 items/day
TERMS_PER_DAY = 5              # 69 terms -> a full pass every 14 days

# How many previously-seen URLs to list in the exclusion prompt. The ledger
# itself grows without limit (pruned by age); this only caps what we paste
# into the prompt, since a 2000-URL exclusion list would dominate the context
# window and cost more than the search it saves.
MAX_EXCLUSIONS_IN_PROMPT = 150
SEEN_RETENTION_DAYS = 180

# A paused turn is not a finished turn. See common.call_with_search.
MAX_SEARCH_TURNS = 10
MAX_TOKENS = 16000

# --- paths ----------------------------------------------------------------

ROOT = os.path.dirname(os.path.abspath(__file__))

ACRONYMS_FILE = os.path.join(ROOT, "acronyms.json")      # gitignored, from secret
SEEN_FILE = os.path.join(ROOT, "data", "seen.json")      # committed, public URLs
PROGRESS_FILE = os.path.join(ROOT, "data", "progress.json")  # committed, indices only

RUN_DIR = os.path.join(ROOT, "data", "run")              # gitignored scratch
BRIEFS_DIR = os.path.join(ROOT, "data", "briefs")        # committed, research only
PRIVATE_DIR = os.path.join(ROOT, "data", "private")      # gitignored, glossary
DOCS_DIR = os.path.join(ROOT, "docs")                    # committed, served by Pages

SITE_URL = os.environ.get("SITE_URL", "https://100badreasons.github.io/learning-agent")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "badwithoutreason@gmail.com")

GMAIL_TOKEN_FILE = os.path.join(ROOT, "gmail_token.json")
GMAIL_CREDENTIALS_FILE = os.path.join(ROOT, "gmail_credentials.json")
GMAIL_SCOPES = [
    # gmail.compose covers messages.send as well as drafts, so the existing
    # bwr-pipeline token works here unchanged — do not widen this, or the
    # token stops matching and Google forces fresh consent.
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def today():
    """Single source of the run's date, so every stage agrees on the filename."""
    return os.environ.get("BRIEF_DATE") or date.today().isoformat()
