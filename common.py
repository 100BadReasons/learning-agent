"""
Shared plumbing: Claude calls, JSON parsing, and the small on-disk ledgers.

Nothing here makes editorial decisions — that's each stage's job.
"""

import json
import os
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import anthropic

import config

# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}


def call_claude(prompt, use_search=False, max_tokens=None):
    """One Claude call, resumed across paused turns, returning the joined text.

    The web_search tool runs server-side, so a single .create() usually covers
    the whole search loop — but on a long turn the API returns stop_reason
    "pause_turn" and expects the response handed back so Claude can resume.
    Treating a paused turn as a finished one yields only Claude's opening
    sentence, with no JSON in it. In bwr-pipeline that exact bug made Scout
    report "found 0 vendors" on every run for weeks without ever erroring.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    messages = [{"role": "user", "content": prompt}]
    text_blocks = []
    kwargs = {"tools": [WEB_SEARCH_TOOL]} if use_search else {}

    for _ in range(config.MAX_SEARCH_TURNS):
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=max_tokens or config.MAX_TOKENS,
            messages=messages,
            **kwargs,
        )

        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                "Claude's response was cut off at max_tokens before it finished. "
                "Lower ITEMS_PER_RESEARCH_STAGE / TERMS_PER_DAY in config.py, or "
                "raise MAX_TOKENS."
            )

        text_blocks += [b.text for b in response.content if b.type == "text"]

        if response.stop_reason != "pause_turn":
            return "\n".join(text_blocks).strip()

        messages.append({"role": "assistant", "content": response.content})

    raise RuntimeError(
        f"Claude was still pausing after {config.MAX_SEARCH_TURNS} turns. "
        f"Raise MAX_SEARCH_TURNS in config.py or narrow the prompt."
    )


def parse_json_array(raw_text):
    """Pull a JSON array out of a response that may be fenced or prefaced."""
    start, end = raw_text.find("["), raw_text.rfind("]")
    if start == -1 or end == -1:
        # No array at all rather than a malformed one usually means the turn
        # ended before Claude reached its answer, so say that instead of
        # blaming the JSON.
        print("Response contained no JSON array at all. Raw output:\n", raw_text)
        raise ValueError("no JSON array in response")
    try:
        return json.loads(raw_text[start:end + 1])
    except json.JSONDecodeError:
        print("Could not parse response as JSON. Raw output:\n", raw_text)
        raise


def parse_json_object(raw_text):
    start, end = raw_text.find("{"), raw_text.rfind("}")
    if start == -1 or end == -1:
        print("Response contained no JSON object at all. Raw output:\n", raw_text)
        raise ValueError("no JSON object in response")
    try:
        return json.loads(raw_text[start:end + 1])
    except json.JSONDecodeError:
        print("Could not parse response as JSON. Raw output:\n", raw_text)
        raise


# ---------------------------------------------------------------------------
# Small JSON files
# ---------------------------------------------------------------------------

def read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def stage_output_path(stage):
    return os.path.join(config.RUN_DIR, f"{stage}.json")


def write_stage(stage, data):
    write_json(stage_output_path(stage), data)


def read_stage(stage, default):
    """Read another stage's output, tolerating a stage that failed this run.

    Stages are independent by design: if research_banking dies, the curator
    should still ship a brief with the agentic-AI half rather than nothing.
    """
    return read_json(stage_output_path(stage), default)


# ---------------------------------------------------------------------------
# The seen-URL ledger — the difference between a daily brief and a Groundhog
# Day loop. Without it the research stages re-surface the same well-ranked
# explainers every morning, because that's what "best material on agentic AI"
# returns every time you ask.
# ---------------------------------------------------------------------------

def normalize_url(url):
    """Strip tracking params and trailing slashes so the same page matches itself."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/") or "/"
    # Query strings on article URLs are almost always utm_* / ref / fbclid.
    return urlunsplit((parts.scheme.lower() or "https", host, path, "", "")).lower()


def normalize_title(title):
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def load_seen():
    return read_json(config.SEEN_FILE, {"urls": {}, "titles": {}})


def save_seen(seen):
    """Persist the ledger, dropping entries older than the retention window.

    Unbounded growth would eventually make every run read a multi-megabyte
    JSON file to answer a question about the last few weeks.
    """
    cutoff = (date.today() - timedelta(days=config.SEEN_RETENTION_DAYS)).isoformat()
    for bucket in ("urls", "titles"):
        seen[bucket] = {k: v for k, v in seen[bucket].items() if v >= cutoff}
    write_json(config.SEEN_FILE, seen)


def is_seen(seen, url, title):
    return (normalize_url(url) in seen["urls"]
            or (normalize_title(title) and normalize_title(title) in seen["titles"]))


def mark_seen(seen, url, title, when=None):
    when = when or config.today()
    seen["urls"][normalize_url(url)] = when
    if normalize_title(title):
        seen["titles"][normalize_title(title)] = when


def recent_exclusions(seen, limit=None):
    """The most recently seen URLs, newest first, for pasting into a prompt."""
    limit = limit or config.MAX_EXCLUSIONS_IN_PROMPT
    ordered = sorted(seen["urls"].items(), key=lambda kv: kv[1], reverse=True)
    return [url for url, _ in ordered[:limit]]


def iso_now():
    return datetime.now().astimezone().isoformat(timespec="seconds")
