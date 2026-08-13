"""
Curator stage — compresses the day's raw research into bite-sized cards and
looks for real connections between the glossary and the research.

This is the stage that decides what is public and what is not:

  data/briefs/<date>.json   PUBLIC  — research cards only. Committed, served.
  data/private/<date>.json  PRIVATE — term lessons + cross-links. Email only.

The split is enforced twice: the prompt is told to keep glossary vocabulary
out of the public half, and leak_check() below verifies it independently
before anything is written. Prompts are guidance; the check is the guarantee.
"""

import json
import os
import re

import config
import common

STAGE = "curator"

# Acronyms whose expansion is standard industry vocabulary, not internal
# knowledge. "Statement of Work" and "Software as a Service" appear in normal
# banking and AI writing constantly, so flagging them would fire the guard on
# nearly every brief — and a guard that cries wolf every morning is a guard
# nobody reads. Publishing these costs nothing; what must not appear is the
# organization's own program, tool, and metric names.
#
# A term added to the spreadsheet is protected by DEFAULT — you have to add it
# here to make it public. That's the safe direction for the mistake to run in.
PUBLIC_ACRONYMS = {
    "ACV", "ASP", "AU", "BOM", "CCU", "DORA", "ELA", "FLM", "FTL", "GDPR",
    "IP", "ISV", "OEM", "OM", "OTC", "PaaS", "PM", "PO", "SaaS", "SL",
    "SLO", "SOW", "SRP", "VAD", "VAR", "YtY",
}

# Below this, a definition is too short and too English to match meaningfully
# ("Base Level", "FastPass") — it would hit inside ordinary prose by accident.
MIN_LEAK_LENGTH = 12


def build_prompt(agentic, banking, terms, cycle):
    def render(items):
        return json.dumps(items, indent=2, ensure_ascii=False) if items else "(none found today)"

    term_listing = "\n".join(
        f"- {t.get('acronym')}: {t.get('definition')} — {t.get('plain_english', '')}"
        for t in terms
    ) or "(none today)"

    return f"""
You are the editor of a daily learning brief for one reader: an enterprise
software seller in financial services who is teaching themselves how AI
agents actually work.

You have today's raw research and today's glossary lesson. Produce the edited
brief.

=== AGENTIC AI RESEARCH ===
{render(agentic)}

=== BANKING AI RESEARCH ===
{render(banking)}

=== TODAY'S GLOSSARY TERMS (pass {cycle}) ===
{term_listing}

Produce a JSON object with exactly these keys:

{{
  "intro": "one sentence on what today's material adds up to. If the day is thin, say that honestly rather than inflating it.",
  "cards": [
    {{
      "url": "the item's url, copied exactly from the input",
      "bite": "2-4 sentences. The compression IS the product: someone who reads only this should come away with the actual idea, not a teaser for it. No 'this article discusses'.",
      "read_if": "one line — who should click through, and who can skip it"
    }}
  ],
  "connections": [
    {{
      "term": "the acronym",
      "url": "url of the research item it connects to, or \\"\\" if it connects to the day's theme rather than one item",
      "insight": "2-3 sentences on the real connection"
    }}
  ]
}}

CARDS:
- One card per input item, keyed by its url. Do not invent items, drop items,
  or merge them.
- CRITICAL: `intro`, `bite`, and `read_if` are published to a public website.
  They must not contain the glossary terms, their definitions, or anything
  that reveals the organization's internal vocabulary. Write them as if the
  glossary did not exist. Every connection to it belongs in `connections`,
  which is private.
  (Terms that are public knowledge on their own — GDPR, DORA, SaaS, PaaS,
  OEM, ISV — are fine to use in public text in their ordinary industry sense.
  What must not appear is the internal glossary's own phrasing.)

CONNECTIONS:
- Check every term against the day's material before you answer, including
  the licensing and contract mechanics. Those look unrelated to an AI article
  and often aren't: how a capability is licensed frequently explains how it
  was deployed. On a typical day 1-3 connections are real.
- But only where a connection is REAL. A forced link between an acronym and
  an unrelated article is worse than no link — it teaches a false association
  and it costs the reader trust in every other connection on the page.
- Zero connections on a given day is still a perfectly good answer. Return an
  empty array and move on. Do not reach to hit a number.
- The good ones tend to be structural: a regulation explaining why a
  deployment was scoped the way it was, a licensing model explaining why an
  AI capability ships as a separate SKU, a contract mechanic explaining why a
  bank's rollout stalled at procurement rather than at the technology.

Respond with ONLY the JSON object — no fences, no preamble.
"""


def leak_check(public_text, acronyms):
    """Return glossary definitions that appear verbatim in public-facing text.

    Matches on definitions rather than acronyms: 'SaaS', 'GDPR', and 'IP'
    occur constantly in legitimate AI and banking writing, so flagging
    acronyms would fire on every brief. The sensitive thing is the mapping —
    'Relationship Suggested Volume Price' does not appear in public writing by
    accident.

    This is a backstop, not a security boundary. The real control is upstream:
    the public half of the brief is written from research the model saw
    WITHOUT the glossary in context, so there is nothing to leak by default.
    This catches the case where the curator ignores that instruction anyway.
    """
    haystack = re.sub(r"\s+", " ", public_text.lower())
    hits = []
    for term in acronyms:
        if term.get("acronym") in PUBLIC_ACRONYMS:
            continue
        definition = term.get("definition", "").strip()
        if len(definition) < MIN_LEAK_LENGTH:
            continue
        if re.sub(r"\s+", " ", definition.lower()) in haystack:
            hits.append(f"{term['acronym']}: {definition}")
    return hits


def public_text_of(brief):
    parts = [brief.get("intro", "")]
    for card in brief.get("cards", []):
        parts += [card.get("bite", ""), card.get("read_if", "")]
    return "\n".join(parts)


def main():
    agentic = common.read_stage("agentic", [])
    banking = common.read_stage("banking", [])
    terms_blob = common.read_stage("terms", {"cycle": 0, "terms": []})
    terms = terms_blob.get("terms", [])

    items = agentic + banking
    if not items and not terms:
        raise RuntimeError(
            "Every upstream stage produced nothing — refusing to publish an "
            "empty brief. Check the stage output above for the real failure."
        )

    # Don't let a thinner run overwrite a fuller one for the same day. CI
    # checks out fresh, so data/run/ is empty there: a --skip-research run
    # would otherwise write a zero-card brief over a good one and push it.
    # A re-run that finds MORE is still allowed through, so recovering from a
    # partial failure works without a flag.
    existing_path = os.path.join(config.BRIEFS_DIR, f"{config.today()}.json")
    existing = common.read_json(existing_path, None)
    if existing and len(existing.get("cards", [])) > len(items):
        if not os.environ.get("FORCE_OVERWRITE"):
            raise RuntimeError(
                f"A brief for {config.today()} already exists with "
                f"{len(existing['cards'])} cards; this run has only {len(items)}. "
                f"Refusing to replace it with less. Set FORCE_OVERWRITE=1 if that "
                f"is genuinely what you want."
            )
        print(f"[{STAGE}] FORCE_OVERWRITE set — replacing the existing brief.")

    print(f"[{STAGE}] curating {len(agentic)} agentic + {len(banking)} banking items "
          f"and {len(terms)} terms.")

    raw = common.call_claude(build_prompt(agentic, banking, terms, terms_blob.get("cycle", 1)))
    edited = common.parse_json_object(raw)

    # Rebuild cards from OUR item list, not the model's, so a hallucinated or
    # dropped url cannot change what gets published. The model contributes
    # prose for items we already have; it does not get to choose the lineup.
    edits_by_url = {c.get("url", ""): c for c in edited.get("cards", [])}
    cards = []
    for item in items:
        edit = edits_by_url.get(item["url"], {})
        cards.append({
            "title": item.get("title", ""),
            "url": item["url"],
            "source": item.get("source", ""),
            "published": item.get("published", ""),
            "format": item.get("format", ""),
            "est_minutes": item.get("est_minutes", 0),
            "level": item.get("level", ""),
            "track": item.get("stage", ""),
            # why_it_matters comes from the research stage, which never saw the
            # glossary — which is exactly what makes it a safe fallback below.
            "bite": edit.get("bite") or item.get("why_it_matters", ""),
            "read_if": edit.get("read_if", ""),
            "key_takeaway": item.get("key_takeaway", ""),
        })

    brief = {
        "date": config.today(),
        "generated_at": common.iso_now(),
        "intro": edited.get("intro", ""),
        "cards": cards,
        "counts": {"agentic": len(agentic), "banking": len(banking), "terms": len(terms)},
    }

    # --- the guarantee ----------------------------------------------------
    acronyms = common.read_json(config.ACRONYMS_FILE, [])
    hits = leak_check(public_text_of(brief), acronyms)
    if hits:
        print(f"[{STAGE}] LEAK GUARD: glossary text found in public copy — {hits}")
        brief["intro"] = ""
        for card, item in zip(brief["cards"], items):
            if leak_check(card["bite"] + card["read_if"], acronyms):
                card["bite"] = item.get("why_it_matters", "")
                card["read_if"] = ""
        remaining = leak_check(public_text_of(brief), acronyms)
        if remaining:
            raise RuntimeError(
                f"Glossary text still present in public copy after fallback: "
                f"{remaining}. Refusing to publish."
            )
        print(f"[{STAGE}] LEAK GUARD: fell back to research-stage copy; public half is clean.")

    private = {
        "date": config.today(),
        "cycle": terms_blob.get("cycle", 0),
        "terms": terms,
        "connections": edited.get("connections", []),
    }

    common.write_json(os.path.join(config.BRIEFS_DIR, f"{brief['date']}.json"), brief)
    common.write_json(os.path.join(config.PRIVATE_DIR, f"{brief['date']}.json"), private)
    print(f"[{STAGE}] {len(cards)} cards public, {len(terms)} terms + "
          f"{len(private['connections'])} connections private.")


if __name__ == "__main__":
    main()
