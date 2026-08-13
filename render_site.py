"""
Renders docs/ — the public site GitHub Pages serves.

Rebuilds the WHOLE site from data/briefs/*.json every run, rather than
appending today's page. That makes it idempotent: a template fix applies
retroactively to every archived day, and a half-finished run leaves nothing
inconsistent behind.

Reads only data/briefs/. It has no access path to the glossary, which is the
point — see curator_agent.py for the split. The Key Terms entry in the
sidebar is a placeholder page explaining that; it carries no term content.
"""

import glob
import html
import os
from collections import OrderedDict
from datetime import datetime

import config
import common

TRACKS = OrderedDict([
    ("agentic", "Agentic AI"),
    ("banking", "AI in Banking"),
])

# Sidebar grouping thresholds. Below the first, dates are a flat list; at or
# above it they collapse into months; once there are this many distinct
# months, months themselves collapse into years.
GROUP_BY_MONTH_AFTER_DAYS = 10
GROUP_BY_YEAR_AFTER_MONTHS = 12

STYLE = """
:root {
  --bg: #fbfaf8; --surface: #ffffff; --ink: #1a1a19; --muted: #6b6a66;
  --line: #e3e0da; --accent: #8a4b2a; --accent-soft: #f3ece6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14140f; --surface: #1c1c17; --ink: #eceae4; --muted: #96938b;
    --line: #2e2e26; --accent: #d99a6c; --accent-soft: #26221c;
  }
}
:root[data-theme="dark"] {
  --bg: #14140f; --surface: #1c1c17; --ink: #eceae4; --muted: #96938b;
  --line: #2e2e26; --accent: #d99a6c; --accent-soft: #26221c;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 64rem; margin: 0 auto; padding: 3rem 1.25rem 5rem; }
header { border-bottom: 1px solid var(--line); padding-bottom: 1.5rem; margin-bottom: 2rem; }
h1 { font-size: 1.5rem; letter-spacing: -0.02em; margin: 0 0 0.35rem; }
h1 a { color: inherit; text-decoration: none; }
.tagline { color: var(--muted); font-size: 0.9rem; margin: 0; }

.layout { display: grid; grid-template-columns: 13rem 1fr; gap: 3rem; align-items: start; }
@media (max-width: 820px) {
  .layout { grid-template-columns: 1fr; gap: 2rem; }
  /* Content first on a phone. With the newest month expanded the date list
     runs longer than the viewport, so a nav-first stack would push the brief
     itself below the fold — and reading today's brief is the whole reason
     anyone opens this on a phone. Nav sits at the bottom like a footer. */
  main { order: 1; }
  .side {
    order: 2; position: static;
    border-top: 1px solid var(--line); padding-top: 1.75rem;
  }
}
.side { position: sticky; top: 2rem; font-size: 0.9rem; }
.side h2 {
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--muted); margin: 0 0 0.6rem; font-weight: 600;
}
.side section + section { margin-top: 2rem; }
.side ul { list-style: none; padding: 0; margin: 0; }
.side li { margin: 0 0 0.3rem; }
.side a { color: var(--ink); text-decoration: none; }
.side a:hover { color: var(--accent); }
.side a.on { color: var(--accent); font-weight: 600; }
.side .count { color: var(--muted); font-size: 0.8rem; }
.side details { margin: 0 0 0.3rem; }
.side details ul { padding-left: 0.75rem; margin-top: 0.3rem; }
.side summary {
  cursor: pointer; color: var(--muted); list-style: none;
  font-variant-numeric: tabular-nums;
}
.side summary::-webkit-details-marker { display: none; }
.side summary::before { content: "▸ "; font-size: 0.75em; }
.side details[open] > summary::before { content: "▾ "; }
.side summary:hover { color: var(--accent); }
.side .locked { color: var(--muted); cursor: default; }

.date { color: var(--muted); font-size: 0.9rem; margin: 0; }
.intro { font-size: 1.05rem; margin: 1.25rem 0 2.5rem; }
h2.sec {
  font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--muted); margin: 2.5rem 0 1rem; font-weight: 600;
}
h2.sec:first-of-type { margin-top: 0; }
.card {
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 1.25rem 1.35rem; margin-bottom: 1rem;
}
.card h3 { font-size: 1.05rem; line-height: 1.4; margin: 0 0 0.5rem; letter-spacing: -0.01em; }
.card h3 a { color: var(--ink); text-decoration: none; border-bottom: 2px solid var(--accent-soft); }
.card h3 a:hover { border-bottom-color: var(--accent); }
.meta { color: var(--muted); font-size: 0.8rem; margin: 0 0 0.75rem; }
.meta span + span::before { content: " · "; }
.meta a { color: var(--muted); }
.bite { margin: 0 0 0.75rem; }
.readif {
  margin: 0; font-size: 0.88rem; color: var(--muted);
  border-left: 2px solid var(--line); padding-left: 0.75rem;
}
.empty { color: var(--muted); font-style: italic; }
.note {
  background: var(--accent-soft); border-radius: 10px; padding: 1.25rem 1.35rem;
  font-size: 0.95rem;
}
nav.pager {
  display: flex; justify-content: space-between; gap: 1rem;
  margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--line);
  font-size: 0.9rem;
}
nav.pager a { color: var(--accent); text-decoration: none; }
nav.pager a:hover { text-decoration: underline; }
footer { margin-top: 3.5rem; color: var(--muted); font-size: 0.8rem; }
"""


def esc(text):
    return html.escape(str(text or ""))


def pretty_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%A, %-d %B %Y")
    except ValueError:
        return iso


def short_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%-d %b")
    except ValueError:
        return iso


def month_label(ym):
    try:
        return datetime.strptime(ym, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return ym


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def date_nav(briefs, up, active):
    """Dates list, newest first, collapsing as the archive grows.

    Flat while the archive is small, grouped by month once there are enough
    days to scroll, and grouped by year once there are enough months that the
    month list itself would. <details> gives collapsible groups with no
    JavaScript, so the page stays a static file.
    """
    ordered = sorted(briefs, key=lambda b: b["date"], reverse=True)

    def link(brief):
        on = " class=\"on\"" if brief["date"] == active else ""
        return (f'<li><a href="{up}archive/{brief["date"]}.html"{on}>'
                f'{esc(short_date(brief["date"]))}</a></li>')

    months = OrderedDict()
    for brief in ordered:
        months.setdefault(brief["date"][:7], []).append(brief)

    if len(ordered) < GROUP_BY_MONTH_AFTER_DAYS:
        return "<ul>" + "".join(link(b) for b in ordered) + "</ul>"

    def month_block(ym, entries, open_it):
        return (f'<details{" open" if open_it else ""}>'
                f'<summary>{esc(month_label(ym))} '
                f'<span class="count">{len(entries)}</span></summary>'
                f'<ul>{"".join(link(b) for b in entries)}</ul></details>')

    if len(months) < GROUP_BY_YEAR_AFTER_MONTHS:
        # Newest month open, and whichever month holds the page you're on.
        return "".join(
            month_block(ym, entries, i == 0 or (active or "")[:7] == ym)
            for i, (ym, entries) in enumerate(months.items())
        )

    years = OrderedDict()
    for ym, entries in months.items():
        years.setdefault(ym[:4], []).append((ym, entries))

    blocks = []
    for i, (year, month_list) in enumerate(years.items()):
        total = sum(len(e) for _, e in month_list)
        inner = "".join(
            month_block(ym, entries, (active or "")[:7] == ym)
            for ym, entries in month_list
        )
        open_year = i == 0 or (active or "")[:4] == year
        blocks.append(f'<details{" open" if open_year else ""}>'
                      f'<summary>{esc(year)} <span class="count">{total}</span></summary>'
                      f'<div>{inner}</div></details>')
    return "".join(blocks)


def topic_nav(briefs, up, active):
    items = []
    for track, heading in TRACKS.items():
        n = sum(1 for b in briefs for c in b["cards"] if c.get("track") == track)
        on = " class=\"on\"" if active == track else ""
        items.append(f'<li><a href="{up}topics/{track}.html"{on}>{esc(heading)}</a> '
                     f'<span class="count">{n}</span></li>')
    on = " class=\"on\"" if active == "terms" else ""
    items.append(f'<li><a href="{up}topics/terms.html"{on}>Key Terms</a></li>')
    return "<ul>" + "".join(items) + "</ul>"


def sidebar(briefs, up, active_date=None, active_topic=None):
    return f"""<aside class="side">
  <section>
    <h2>Topics</h2>
    {topic_nav(briefs, up, active_topic)}
  </section>
  <section>
    <h2>Dates</h2>
    {date_nav(briefs, up, active_date)}
  </section>
</aside>"""


# ---------------------------------------------------------------------------
# Cards and pages
# ---------------------------------------------------------------------------

def render_card(card, up=None, show_date=None):
    meta = []
    if card.get("source"):
        meta.append(esc(card["source"]))
    # Kept next to the source and spelled out, matching the email: a bare
    # "2026-05" further down the list reads as just another tag.
    if card.get("published") and card["published"] != "unknown":
        meta.append(f"published {esc(card['published'])}")
    if card.get("format"):
        meta.append(esc(card["format"]))
    if card.get("est_minutes"):
        meta.append(f"{esc(card['est_minutes'])} min")
    if card.get("level"):
        meta.append(esc(card["level"]))
    if show_date:
        meta.append(f'<a href="{up}archive/{show_date}.html">'
                    f'{esc(short_date(show_date))}</a>')

    read_if = (f'<p class="readif">{esc(card["read_if"])}</p>'
               if card.get("read_if") else "")

    return f"""    <article class="card">
      <h3><a href="{esc(card['url'])}" rel="noopener">{esc(card['title'])}</a></h3>
      <p class="meta">{"".join(f"<span>{m}</span>" for m in meta)}</p>
      <p class="bite">{esc(card.get('bite'))}</p>
{read_if}
    </article>"""


def page(title, main, briefs, depth=0, active_date=None, active_topic=None):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{esc(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1><a href="{up}index.html">Daily Learning Brief</a></h1>
  <p class="tagline">Agentic AI &amp; automation in banking</p>
</header>
<div class="layout">
{sidebar(briefs, up, active_date, active_topic)}
<main>
{main}
</main>
</div>
<footer>Generated automatically each morning. Sources link out to the original.</footer>
</div>
</body>
</html>
"""


def render_brief(brief, briefs, prev_date=None, next_date=None, depth=0):
    up = "../" * depth
    sections = []
    for track, heading in TRACKS.items():
        cards = [c for c in brief["cards"] if c.get("track") == track]
        sections.append(f'<h2 class="sec">{heading}</h2>')
        if cards:
            sections.append("\n".join(render_card(c) for c in cards))
        else:
            sections.append('<p class="empty">Nothing new worth your time today.</p>')

    intro = f'<p class="intro">{esc(brief["intro"])}</p>' if brief.get("intro") else ""

    links = []
    links.append(f'<a href="{up}archive/{prev_date}.html">&larr; {prev_date}</a>'
                 if prev_date else "<span></span>")
    links.append(f'<a href="{up}archive/index.html">All briefs</a>')
    links.append(f'<a href="{up}archive/{next_date}.html">{next_date} &rarr;</a>'
                 if next_date else "<span></span>")

    main = f"""<p class="date">{esc(pretty_date(brief['date']))}</p>
{intro}
{"".join(sections)}
<nav class="pager">{"".join(links)}</nav>"""

    return page(f"Learning Brief — {brief['date']}", main, briefs,
                depth=depth, active_date=brief["date"])


def render_topic(track, heading, briefs):
    """Every card ever published in one track, newest brief first."""
    up = "../"
    blocks = []
    total = 0
    for brief in sorted(briefs, key=lambda b: b["date"], reverse=True):
        cards = [c for c in brief["cards"] if c.get("track") == track]
        total += len(cards)
        blocks += [render_card(c, up=up, show_date=brief["date"]) for c in cards]

    body = ("\n".join(blocks) if blocks
            else '<p class="empty">Nothing here yet.</p>')
    main = (f'<h2 class="sec">{esc(heading)}</h2>'
            f'<p class="date">{total} item{"s" if total != 1 else ""} '
            f'across {len(briefs)} brief{"s" if len(briefs) != 1 else ""}.</p>'
            f'<div style="margin-top:1.5rem">{body}</div>')
    return page(f"{heading} — Learning Brief", main, briefs,
                depth=1, active_topic=track)


def render_terms_page(briefs):
    """Placeholder for the Key Terms topic.

    The glossary is internal terminology and is delivered by email only, so
    this page deliberately contains none of it — it exists so the sidebar can
    show all three categories without the site holding the content.
    """
    main = """<h2 class="sec">Key Terms</h2>
<div class="note">
  <p style="margin:0 0 0.75rem"><strong>Delivered by email, not published here.</strong></p>
  <p style="margin:0">The glossary lesson — five terms a day, plus the connections
  between them and the day's research — goes out in the daily email. It is
  internal terminology, so it is deliberately kept off this public site and out
  of the repository behind it.</p>
</div>"""
    return page("Key Terms — Learning Brief", main, briefs,
                depth=1, active_topic="terms")


def render_archive_index(briefs):
    rows = []
    for brief in sorted(briefs, key=lambda b: b["date"], reverse=True):
        n = len(brief["cards"])
        rows.append(f'<li style="border-bottom:1px solid var(--line);padding:0.7rem 0;'
                    f'display:flex;gap:1rem;">'
                    f'<a href="{brief["date"]}.html" style="color:var(--ink);'
                    f'text-decoration:none;">{esc(pretty_date(brief["date"]))}</a>'
                    f'<span class="count" style="margin-left:auto;">'
                    f'{n} item{"s" if n != 1 else ""}</span></li>')
    main = ('<h2 class="sec">All briefs</h2><ul style="list-style:none;padding:0;margin:0;">'
            + "".join(rows) + "</ul>") if rows else '<p class="empty">No briefs yet.</p>'
    return page("Archive — Learning Brief", main, briefs, depth=1)


def main():
    paths = sorted(glob.glob(os.path.join(config.BRIEFS_DIR, "*.json")))
    briefs = [b for b in (common.read_json(p, None) for p in paths) if b]
    if not briefs:
        print("[site] no briefs to render.")
        return

    for sub in ("archive", "topics"):
        os.makedirs(os.path.join(config.DOCS_DIR, sub), exist_ok=True)

    for i, brief in enumerate(briefs):
        prev_date = briefs[i - 1]["date"] if i > 0 else None
        next_date = briefs[i + 1]["date"] if i < len(briefs) - 1 else None
        path = os.path.join(config.DOCS_DIR, "archive", f"{brief['date']}.html")
        with open(path, "w") as f:
            f.write(render_brief(brief, briefs, prev_date, next_date, depth=1))

    latest = briefs[-1]
    prev_date = briefs[-2]["date"] if len(briefs) > 1 else None
    with open(os.path.join(config.DOCS_DIR, "index.html"), "w") as f:
        f.write(render_brief(latest, briefs, prev_date, None, depth=0))

    for track, heading in TRACKS.items():
        with open(os.path.join(config.DOCS_DIR, "topics", f"{track}.html"), "w") as f:
            f.write(render_topic(track, heading, briefs))
    with open(os.path.join(config.DOCS_DIR, "topics", "terms.html"), "w") as f:
        f.write(render_terms_page(briefs))

    with open(os.path.join(config.DOCS_DIR, "archive", "index.html"), "w") as f:
        f.write(render_archive_index(briefs))

    with open(os.path.join(config.DOCS_DIR, ".nojekyll"), "w") as f:
        f.write("")

    months = len({b["date"][:7] for b in briefs})
    grouping = ("flat" if len(briefs) < GROUP_BY_MONTH_AFTER_DAYS
                else "by year" if months >= GROUP_BY_YEAR_AFTER_MONTHS
                else "by month")
    print(f"[site] rendered {len(briefs)} brief(s); latest is {latest['date']}; "
          f"date nav is {grouping}.")


if __name__ == "__main__":
    main()
