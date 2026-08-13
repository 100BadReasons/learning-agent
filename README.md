# Daily Learning Brief

A scheduled pipeline that researches agentic AI and AI/automation in banking,
teaches a rotating slice of a private glossary, edits it all into a short
daily brief, publishes the public half to GitHub Pages, and emails the whole
thing.

Runs itself every morning at 11:00 UTC. No agent session, no MCP connection,
no interactive approval — it is plain Python on a GitHub Actions cron.

## What it produces

| Where | What | Visibility |
|---|---|---|
| `docs/` → GitHub Pages | Research cards, linking out to sources | **Public** |
| Daily email (primary) | Everything above **plus** the glossary lesson and cross-links | Private |
| Daily email (extra recipients) | Research cards only, no glossary | Private |

The site has a sidebar with two axes: **Dates**, newest first — a flat list
until there are 10 briefs, then grouped by month, then by year once there are
12 months — and **Topics**, which collect every card ever published in a
track. Key Terms appears there too, as a page explaining that the glossary is
email-only.

## The public/private split

This repo is public, because GitHub Pages is only free on public repos.
The glossary is internal sales/licensing terminology and is **never
committed**: it arrives at runtime, base64-decoded from the `ACRONYMS_JSON`
secret, and is gitignored.

Three things enforce the split:

1. `.gitignore` excludes `acronyms.json*` and `data/private/`.
2. `curator_agent.leak_check()` scans the public half for glossary
   definitions before writing, and falls back to research-stage copy if it
   finds any. See that function for why it matches on definitions rather
   than acronyms.
3. The Publish step in the workflow re-verifies the ignore rules before it
   pushes, because that job holds the decrypted secret on disk.

The primary control is upstream of all three: the public copy is written from
research the model saw *without* the glossary in context.

## Stages

```
research_agentic.py ─┐
research_banking.py ─┼─→ curator_agent.py ─→ render_site.py ─→ notify.py
terms_agent.py      ─┘
```

Stages 1–3 are independent — any can fail and the day still ships. Stages
4–6 are a chain: if the curator fails there is no new brief, so re-rendering
and emailing would just resend yesterday's. The chain aborts and the run
exits non-zero instead.

## Local use

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
python bootstrap_acronyms.py ~/Downloads/Acronym_Soup.xlsx
echo "ANTHROPIC_API_KEY=sk-..." > .env
./venv/bin/python orchestrator.py --no-notify
```

Flags: `--skip-research` (cheap run, no search credits), `--no-notify`,
`--local`. `python render_email.py` writes an email preview to the gitignored
`data/run/`.

## Tuning

Everything that affects cost or reading length is in `config.py`:
`ITEMS_PER_RESEARCH_STAGE`, `TERMS_PER_DAY`, `MAX_TOKENS`. What actually gets
found is governed by the `TOPIC_BRIEF` in each research module — those are
the editorial policy, and they are meant to be edited.

## Recipients

The primary recipient (`NOTIFY_EMAIL`) gets the full brief. Anyone else gets a
research-only edition with no term lessons and no cross-links, so adding a
colleague can never forward internal terminology. Each recipient is mailed
separately — a reading list should not leak everyone's address to everyone.

```bash
python recipients.py add colleague@example.com
python recipients.py list
python recipients.py push    # syncs to the RECIPIENTS_JSON secret
```

`recipients.json` is gitignored: addresses are personal data and this repo is
public. Secrets are write-only, so the local file is the source of truth and
`push` overwrites the secret with all of it — always `list` before you `push`.

## Secrets

| Secret | What |
|---|---|
| `ANTHROPIC_API_KEY` | API key |
| `ACRONYMS_JSON` | base64 of `acronyms.json` |
| `GMAIL_TOKEN_JSON` | base64 of `gmail_token.json` |
| `GMAIL_CREDENTIALS_JSON` | base64 of `gmail_credentials.json` |
| `NOTIFY_EMAIL` | primary destination address |
| `RECIPIENTS_JSON` | base64 of `recipients.json` (optional) |

If the daily email stops arriving, the Gmail refresh token has most likely
expired. `notify.py` fails loudly with the exact re-mint command rather than
letting the run go green with nothing delivered.
