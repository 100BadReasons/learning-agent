"""
Renders the daily email — the FULL brief, including the glossary lesson and
the cross-links that the public site deliberately omits.

Written with inline styles and table-free markup because Gmail strips much of
a <style> block, and committed to no file: the HTML is handed straight to
notify.py in memory so the glossary never lands on disk in the repo.

Deliberately light-mode only. Email dark-mode handling is inconsistent across
clients and a half-inverted palette reads worse than a fixed one.
"""

import glob
import html
import os

import config
import common
from render_site import TRACKS, pretty_date

INK = "#1a1a19"
MUTED = "#6b6a66"
LINE = "#e3e0da"
ACCENT = "#8a4b2a"
SOFT = "#f7f4f0"


def esc(text):
    return html.escape(str(text or ""))


def h2(text):
    return (f'<h2 style="font-size:12px;text-transform:uppercase;letter-spacing:1.2px;'
            f'color:{MUTED};margin:34px 0 12px;font-weight:600;">{esc(text)}</h2>')


def render_card(card):
    meta = [m for m in [card.get("source"), card.get("format"),
                        f"{card['est_minutes']} min" if card.get("est_minutes") else None,
                        card.get("level")] if m]
    read_if = ""
    if card.get("read_if"):
        read_if = (f'<p style="margin:8px 0 0;font-size:13px;color:{MUTED};'
                   f'border-left:2px solid {LINE};padding-left:10px;">'
                   f'{esc(card["read_if"])}</p>')
    return f"""
<div style="border:1px solid {LINE};border-radius:8px;padding:16px 18px;margin-bottom:12px;">
  <a href="{esc(card['url'])}" style="color:{INK};text-decoration:none;font-size:16px;
     font-weight:600;line-height:1.4;">{esc(card['title'])}</a>
  <p style="margin:6px 0 10px;font-size:12px;color:{MUTED};">{esc(" · ".join(meta))}</p>
  <p style="margin:0;font-size:15px;line-height:1.6;color:{INK};">{esc(card.get('bite'))}</p>
  {read_if}
</div>"""


def render_term(term):
    rows = [
        ("In plain English", term.get("plain_english")),
        ("Why it matters", term.get("why_it_matters")),
        ("Example", term.get("example")),
        ("Watch out", term.get("gotcha")),
    ]
    body = "".join(
        f'<p style="margin:0 0 8px;font-size:14px;line-height:1.6;color:{INK};">'
        f'<strong style="color:{MUTED};font-size:12px;text-transform:uppercase;'
        f'letter-spacing:0.6px;">{esc(label)}</strong><br>{esc(value)}</p>'
        for label, value in rows if value
    )
    return f"""
<div style="background:{SOFT};border-radius:8px;padding:16px 18px;margin-bottom:12px;">
  <p style="margin:0 0 4px;font-size:17px;font-weight:700;color:{INK};">
    {esc(term.get('acronym'))}</p>
  <p style="margin:0 0 12px;font-size:13px;color:{ACCENT};">
    {esc(term.get('definition'))}</p>
  {body}
</div>"""


def render_connection(conn, cards_by_url):
    target = cards_by_url.get(conn.get("url", ""))
    link = ""
    if target:
        link = (f'<p style="margin:8px 0 0;font-size:13px;">'
                f'<a href="{esc(target["url"])}" style="color:{ACCENT};">'
                f'{esc(target["title"])}</a></p>')
    return f"""
<div style="border-left:3px solid {ACCENT};padding:2px 0 2px 14px;margin-bottom:16px;">
  <p style="margin:0 0 4px;font-size:14px;font-weight:700;color:{INK};">
    {esc(conn.get('term'))}</p>
  <p style="margin:0;font-size:14px;line-height:1.6;color:{INK};">
    {esc(conn.get('insight'))}</p>
  {link}
</div>"""


def build(brief, private):
    cards_by_url = {c["url"]: c for c in brief["cards"]}

    sections = []
    for track, heading in TRACKS.items():
        cards = [c for c in brief["cards"] if c.get("track") == track]
        sections.append(h2(heading))
        if cards:
            sections.append("".join(render_card(c) for c in cards))
        else:
            sections.append(f'<p style="color:{MUTED};font-style:italic;font-size:14px;">'
                            f'Nothing new worth your time today.</p>')

    if private.get("terms"):
        pass_note = ""
        if private.get("cycle", 1) > 1:
            pass_note = (f' <span style="font-weight:400;text-transform:none;'
                         f'letter-spacing:0;">(pass {private["cycle"]} — going deeper)</span>')
        sections.append(h2("Terms").replace("</h2>", f"{pass_note}</h2>"))
        sections.append("".join(render_term(t) for t in private["terms"]))

    if private.get("connections"):
        sections.append(h2("How these connect"))
        sections.append("".join(render_connection(c, cards_by_url)
                                for c in private["connections"]))

    if brief.get("intro"):
        sections.insert(0, f'<p style="font-size:16px;line-height:1.6;color:{INK};'
                           f'margin:0 0 8px;">{esc(brief["intro"])}</p>')

    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#fbfaf8;">
<div style="max-width:640px;margin:0 auto;padding:28px 20px 48px;
     font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <p style="margin:0 0 2px;font-size:20px;font-weight:700;color:{INK};
     letter-spacing:-0.3px;">Daily Learning Brief</p>
  <p style="margin:0 0 22px;font-size:13px;color:{MUTED};">
    {esc(pretty_date(brief['date']))} &nbsp;·&nbsp;
    <a href="{esc(config.SITE_URL)}" style="color:{ACCENT};">view on the web</a>
  </p>
  {"".join(sections)}
  <p style="margin:36px 0 0;padding-top:16px;border-top:1px solid {LINE};
     font-size:12px;color:{MUTED};">
    The Terms and How-these-connect sections are in this email only — they are
    not published to the public site.
  </p>
</div>
</body></html>"""


def latest_brief():
    """Today's brief if there is one, else the most recent — so a re-run after
    a failed publish still emails something real rather than crashing."""
    date = config.today()
    public_path = os.path.join(config.BRIEFS_DIR, f"{date}.json")
    if not os.path.exists(public_path):
        paths = sorted(glob.glob(os.path.join(config.BRIEFS_DIR, "*.json")))
        if not paths:
            raise RuntimeError("No briefs exist — nothing to email.")
        public_path = paths[-1]
        date = os.path.basename(public_path)[:-5]
        print(f"[email] no brief for {config.today()}; falling back to {date}.")

    brief = common.read_json(public_path, None)
    private = common.read_json(os.path.join(config.PRIVATE_DIR, f"{date}.json"),
                               {"terms": [], "connections": [], "cycle": 0})
    return brief, private


def main():
    brief, private = latest_brief()
    return build(brief, private)


if __name__ == "__main__":
    # Preview lands in the gitignored scratch dir — it contains the glossary.
    out = os.path.join(config.RUN_DIR, "preview_email.html")
    os.makedirs(config.RUN_DIR, exist_ok=True)
    with open(out, "w") as f:
        f.write(main())
    print(f"Wrote preview to {out} (gitignored).")
