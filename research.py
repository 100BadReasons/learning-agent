"""
Shared research engine for the two web-research stages.

The stages differ only in what they're looking for, so the search loop,
dedupe, and validation live here and each stage supplies a topic brief.
"""

import config
import common

ITEM_SCHEMA = """{
  "title": "",
  "url": "",
  "source": "publication or author",
  "published": "YYYY-MM, or \\"unknown\\" if you genuinely cannot tell",
  "format": "article | paper | video | course | repo | podcast | docs",
  "est_minutes": 0,
  "level": "intro | working | deep",
  "why_it_matters": "1-2 sentences, specific to this reader",
  "key_takeaway": "the single most useful idea in it, stated plainly"
}"""


def build_prompt(topic_brief, exclusions, target):
    exclusion_list = "\n".join(f"- {u}" for u in exclusions) or "(nothing yet — this is the first run)"

    return f"""
You are a research assistant building one day's worth of learning material.
Use web search to find up to {target} genuinely useful, genuinely NEW items.

{target} is a ceiling, not a quota. Returning 3 excellent items beats padding
to {target} with generic listicles or vendor marketing. If a search day is
thin, return fewer and say nothing about it.

{topic_brief}

ALREADY DELIVERED — do not return any of these URLs, or a different URL that
points at substantially the same piece (a syndicated copy, an AMP version, a
newsletter reprint):
{exclusion_list}

Quality bar:
- Verify each URL through search. Never construct a plausible-looking URL.
- Prefer primary sources: the lab's own paper, the vendor's own docs, the
  practitioner's own writeup — over a news article summarizing one.
- Prefer material from the last 12 months unless something older is genuinely
  foundational and still accurate.
- Mix the formats. A day of nothing but blog posts is a worse day than one
  with a paper, a talk, and a hands-on tutorial.
- Skip anything paywalled at the first click, and skip pure product
  announcements with no teaching content in them.

Respond with ONLY a JSON array (no markdown fences, no preamble, no closing
commentary), where each item has exactly these fields:
{ITEM_SCHEMA}

est_minutes is your honest estimate of time to consume it. Leave a string
field empty rather than inventing a value you did not verify.
"""


def run(stage, topic_brief, target=None):
    """Research one topic, drop anything already delivered, save for the curator."""
    target = target or config.ITEMS_PER_RESEARCH_STAGE

    seen = common.load_seen()
    exclusions = common.recent_exclusions(seen)
    print(f"[{stage}] {len(seen['urls'])} URLs in the ledger, "
          f"{len(exclusions)} passed to the prompt as exclusions.")

    raw = common.call_claude(build_prompt(topic_brief, exclusions, target), use_search=True)
    items = common.parse_json_array(raw)

    # Filter again on our side. The exclusion list is capped and Claude is not
    # a database — client-side filtering is what actually guarantees the
    # promise, the same way scout_agent re-filters its candidates.
    fresh, repeats = [], 0
    for item in items:
        url, title = item.get("url", "").strip(), item.get("title", "").strip()
        if not url or not title:
            print(f"[{stage}] dropping item with no url or title: {item!r}")
            continue
        if common.is_seen(seen, url, title):
            repeats += 1
            continue
        item["stage"] = stage
        fresh.append(item)

    print(f"[{stage}] Claude returned {len(items)}; {repeats} already delivered; "
          f"{len(fresh)} new.")

    # The ledger is only updated once an item survives filtering, so an item
    # dropped for a missing URL can still be found again tomorrow.
    for item in fresh:
        common.mark_seen(seen, item["url"], item["title"])
    common.save_seen(seen)

    common.write_stage(stage, fresh)
    return fresh
