"""
Renders docs/ — the public site GitHub Pages serves.

Rebuilds the WHOLE site from data/briefs/*.json every run, rather than
appending today's page. That makes it idempotent: a template fix applies
retroactively to every archived day, and a half-finished run leaves nothing
inconsistent behind.

Reads only data/briefs/. It has no access path to the glossary, which is the
point — see curator_agent.py for the split.
"""

import glob
import html
import os
from datetime import datetime

import config
import common

TRACKS = {
    "agentic": "Agentic AI",
    "banking": "AI in Banking",
}

STYLE = """
:root {
  --bg: #fbfaf8; --surface: #ffffff; --ink: #1a1a19; --muted: #6b6a66;
  --line: #e3e0da; --accent: #8a4b2a; --accent-soft: #f3ece6;
}
:root:not([data-theme="light"]) { }
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
.wrap { max-width: 46rem; margin: 0 auto; padding: 3rem 1.25rem 5rem; }
header { border-bottom: 1px solid var(--line); padding-bottom: 1.5rem; margin-bottom: 2rem; }
h1 { font-size: 1.5rem; letter-spacing: -0.02em; margin: 0 0 0.35rem; }
h1 a { color: inherit; text-decoration: none; }
.date { color: var(--muted); font-size: 0.9rem; margin: 0; }
.intro { font-size: 1.05rem; margin: 1.5rem 0 2.5rem; color: var(--ink); }
h2 {
  font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--muted); margin: 2.75rem 0 1rem; font-weight: 600;
}
.card {
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 1.25rem 1.35rem; margin-bottom: 1rem;
}
.card h3 { font-size: 1.05rem; line-height: 1.4; margin: 0 0 0.5rem; letter-spacing: -0.01em; }
.card h3 a { color: var(--ink); text-decoration: none; border-bottom: 2px solid var(--accent-soft); }
.card h3 a:hover { border-bottom-color: var(--accent); }
.meta { color: var(--muted); font-size: 0.8rem; margin: 0 0 0.75rem; }
.meta span + span::before { content: " · "; }
.bite { margin: 0 0 0.75rem; }
.readif {
  margin: 0; font-size: 0.88rem; color: var(--muted);
  border-left: 2px solid var(--line); padding-left: 0.75rem;
}
.empty { color: var(--muted); font-style: italic; }
nav.pager {
  display: flex; justify-content: space-between; gap: 1rem;
  margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--line);
  font-size: 0.9rem;
}
nav.pager a { color: var(--accent); text-decoration: none; }
nav.pager a:hover { text-decoration: underline; }
ul.archive { list-style: none; padding: 0; margin: 0; }
ul.archive li { border-bottom: 1px solid var(--line); padding: 0.7rem 0; display: flex; gap: 1rem; }
ul.archive a { color: var(--ink); text-decoration: none; font-variant-numeric: tabular-nums; }
ul.archive a:hover { color: var(--accent); }
ul.archive .n { color: var(--muted); font-size: 0.85rem; margin-left: auto; }
footer { margin-top: 3.5rem; color: var(--muted); font-size: 0.8rem; }
"""


def esc(text):
    return html.escape(str(text or ""))


def pretty_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%A, %-d %B %Y")
    except ValueError:
        return iso


def render_card(card):
    meta = []
    if card.get("source"):
        meta.append(esc(card["source"]))
    if card.get("format"):
        meta.append(esc(card["format"]))
    if card.get("est_minutes"):
        meta.append(f"{esc(card['est_minutes'])} min")
    if card.get("level"):
        meta.append(esc(card["level"]))
    if card.get("published") and card["published"] != "unknown":
        meta.append(esc(card["published"]))

    read_if = (f'<p class="readif">{esc(card["read_if"])}</p>'
               if card.get("read_if") else "")

    return f"""    <article class="card">
      <h3><a href="{esc(card['url'])}" rel="noopener">{esc(card['title'])}</a></h3>
      <p class="meta">{"".join(f"<span>{m}</span>" for m in meta)}</p>
      <p class="bite">{esc(card.get('bite'))}</p>
{read_if}
    </article>"""


def page(title, body, depth=0):
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
  <p class="date">Agentic AI &amp; automation in banking</p>
</header>
{body}
<footer>Generated automatically each morning. Sources link out to the original.</footer>
</div>
</body>
</html>
"""


def render_brief(brief, prev_date=None, next_date=None, depth=0):
    up = "../" * depth
    sections = []
    for track, heading in TRACKS.items():
        cards = [c for c in brief["cards"] if c.get("track") == track]
        if not cards:
            sections.append(f'<h2>{heading}</h2>\n<p class="empty">'
                            f'Nothing new worth your time today.</p>')
            continue
        sections.append(f"<h2>{heading}</h2>\n" + "\n".join(render_card(c) for c in cards))

    intro = f'<p class="intro">{esc(brief["intro"])}</p>' if brief.get("intro") else ""

    links = []
    if prev_date:
        links.append(f'<a href="{up}archive/{prev_date}.html">&larr; {prev_date}</a>')
    else:
        links.append("<span></span>")
    links.append(f'<a href="{up}archive/index.html">All briefs</a>')
    if next_date:
        links.append(f'<a href="{up}archive/{next_date}.html">{next_date} &rarr;</a>')
    else:
        links.append("<span></span>")

    body = f"""<p class="date">{esc(pretty_date(brief['date']))}</p>
{intro}
{"".join(sections)}
<nav class="pager">{"".join(links)}</nav>"""

    return page(f"Learning Brief — {brief['date']}", body, depth=depth)


def render_archive_index(briefs):
    rows = []
    for brief in briefs:
        n = len(brief["cards"])
        rows.append(f'  <li><a href="{brief["date"]}.html">{esc(pretty_date(brief["date"]))}</a>'
                    f'<span class="n">{n} item{"s" if n != 1 else ""}</span></li>')
    body = ("<h2>All briefs</h2>\n<ul class=\"archive\">\n" + "\n".join(rows) + "\n</ul>"
            if rows else '<p class="empty">No briefs yet.</p>')
    return page("Learning Brief — Archive", body, depth=1)


def main():
    paths = sorted(glob.glob(os.path.join(config.BRIEFS_DIR, "*.json")))
    briefs = [common.read_json(p, None) for p in paths]
    briefs = [b for b in briefs if b]
    if not briefs:
        print("[site] no briefs to render.")
        return

    os.makedirs(os.path.join(config.DOCS_DIR, "archive"), exist_ok=True)

    for i, brief in enumerate(briefs):
        prev_date = briefs[i - 1]["date"] if i > 0 else None
        next_date = briefs[i + 1]["date"] if i < len(briefs) - 1 else None
        path = os.path.join(config.DOCS_DIR, "archive", f"{brief['date']}.html")
        with open(path, "w") as f:
            f.write(render_brief(brief, prev_date, next_date, depth=1))

    latest = briefs[-1]
    prev_date = briefs[-2]["date"] if len(briefs) > 1 else None
    with open(os.path.join(config.DOCS_DIR, "index.html"), "w") as f:
        f.write(render_brief(latest, prev_date, None, depth=0))

    with open(os.path.join(config.DOCS_DIR, "archive", "index.html"), "w") as f:
        f.write(render_archive_index(list(reversed(briefs))))

    # Pages would otherwise run the whole directory through Jekyll, which
    # silently drops any file or folder whose name starts with an underscore.
    with open(os.path.join(config.DOCS_DIR, ".nojekyll"), "w") as f:
        f.write("")

    print(f"[site] rendered {len(briefs)} brief(s); latest is {latest['date']}.")


if __name__ == "__main__":
    main()
