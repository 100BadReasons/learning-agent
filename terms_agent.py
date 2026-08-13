"""
Terms stage — teaches the next few acronyms from the glossary.

Output from this stage is PRIVATE. It quotes the glossary verbatim, so it
goes only into the email, never into docs/ and never into data/briefs/.
See .gitignore.

Rotation is tracked by index, not by term text, so data/progress.json can sit
in a public repo without leaking anything: a list of integers means nothing
without the secret it indexes into.

No web search here — the definitions are supplied, and a search per term
would roughly double the daily bill to re-derive what the spreadsheet
already says. Flip use_search=True in run_lesson if you ever want sourced
context instead.
"""

import json
import os
import random

import config
import common

STAGE = "terms"


def load_acronyms():
    if not os.path.exists(config.ACRONYMS_FILE):
        raise RuntimeError(
            f"{config.ACRONYMS_FILE} is missing. Locally, run:\n"
            f"  python bootstrap_acronyms.py ~/Downloads/Acronym_Soup.xlsx\n"
            f"In CI it is decoded from the ACRONYMS_JSON secret — if this fires "
            f"there, that secret is unset or is not valid base64."
        )
    with open(config.ACRONYMS_FILE) as f:
        return json.load(f)


def next_indices(total, count):
    """Pick the next `count` glossary positions, advancing the rotation.

    Each cycle walks a shuffled permutation of every term, so you get the
    whole glossary before seeing any term twice. The shuffle is seeded on the
    cycle number, which keeps a re-run of the same day reproducible instead
    of silently reshuffling the queue underneath you.
    """
    progress = common.read_json(config.PROGRESS_FILE, {"cycle": 0, "order": [], "next": 0})

    if not progress["order"] or progress["next"] >= len(progress["order"]):
        progress["cycle"] += 1
        order = list(range(total))
        random.Random(progress["cycle"]).shuffle(order)
        progress["order"] = order
        progress["next"] = 0
        print(f"[{STAGE}] starting cycle {progress['cycle']} over {total} terms.")

    # A term added to the spreadsheet mid-cycle would sit outside the current
    # permutation; it gets picked up when the next cycle reshuffles.
    order = [i for i in progress["order"] if i < total]
    start = progress["next"]
    picked = order[start:start + count]
    progress["next"] = start + len(picked)

    common.write_json(config.PROGRESS_FILE, progress)
    return picked, progress["cycle"]


def build_prompt(terms, cycle):
    listing = "\n".join(f"- {t['acronym']}: {t['definition']}" for t in terms)

    if cycle == 1:
        mode = """
This is the reader's FIRST time seeing these terms. Teach each one properly.
"""
    else:
        mode = f"""
This is pass {cycle} — the reader has seen every one of these before. Do not
just repeat the definition. Go a level deeper: the edge case, the way it
interacts with the other terms, the thing that trips people up in month six
rather than week one.
"""

    return f"""
You are teaching an enterprise software seller the vocabulary of their own
business. These are IBM software sales, licensing, and renewals terms.
{mode}
The reader is competent and busy. No throat-clearing, no "great question",
no restating the acronym back at them as if that were an explanation.

TERMS FOR TODAY:
{listing}

The supplied definition is authoritative — it is their organization's own
glossary. If your understanding differs, teach theirs and note the difference
in `gotcha` rather than silently overriding it.

For each term, respond with an object containing exactly these fields:
{{
  "acronym": "",
  "definition": "the supplied definition, verbatim",
  "plain_english": "what it actually means, 1-2 sentences, no jargon",
  "why_it_matters": "why a seller needs this — what breaks if they get it wrong",
  "example": "one concrete scenario using it the way a colleague would",
  "gotcha": "the confusion, edge case, or adjacent term people mix it up with"
}}

If a term is genuinely ambiguous or you are not confident what it refers to
in this specific context, say so plainly in `gotcha` rather than inventing
authoritative-sounding detail. Being wrong here is worse than being brief.

Respond with ONLY a JSON array of those objects — no fences, no preamble.
"""


def main():
    acronyms = load_acronyms()
    indices, cycle = next_indices(len(acronyms), config.TERMS_PER_DAY)

    if not indices:
        print(f"[{STAGE}] no terms to teach — the glossary is empty.")
        common.write_stage(STAGE, {"cycle": cycle, "terms": []})
        return

    todays = [acronyms[i] for i in indices]
    print(f"[{STAGE}] cycle {cycle}, teaching: {', '.join(t['acronym'] for t in todays)}")

    raw = common.call_claude(build_prompt(todays, cycle))
    lessons = common.parse_json_array(raw)

    # Trust the glossary over the model for the one field we already know.
    by_acronym = {t["acronym"]: t["definition"] for t in todays}
    for lesson in lessons:
        if lesson.get("acronym") in by_acronym:
            lesson["definition"] = by_acronym[lesson["acronym"]]

    common.write_stage(STAGE, {"cycle": cycle, "terms": lessons})
    print(f"[{STAGE}] wrote {len(lessons)} lessons.")


if __name__ == "__main__":
    main()
