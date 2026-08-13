"""
Orchestrator — daily learning pipeline

Runs the full cycle in sequence:

  1. Research: Agentic AI      — web search, deduped against the seen ledger
  2. Research: AI in banking   — same
  3. Terms                     — next slice of the glossary rotation
  4. Curator                   — edits everything into cards + cross-links,
                                 and splits public from private
  5. Site                      — rebuilds docs/ from every archived brief
  6. Notify                    — emails the full brief, glossary included

Stages 1-3 are INDEPENDENT: any of them can fail and the day still ships with
whatever the others produced. Stages 4-6 are a CHAIN: if the curator fails
there is no new brief, so re-rendering the site and emailing would just
resend yesterday's — worse than nothing, because it looks like success. The
chain aborts instead and the run exits non-zero.

This is a self-contained script. It needs no Claude Code session, no MCP
connection, and no interactive approval — which is the whole point. The
predecessor pipeline was scheduled as an agent turn and died on a Bash
permission prompt on every single unattended run, with nobody there to
answer it. Run this from cron or GitHub Actions.

Usage:
  python orchestrator.py                 # full run
  python orchestrator.py --skip-research # terms + curate + render only (cheap)
  python orchestrator.py --no-notify     # build and publish, send no email
  python orchestrator.py --local         # no notify, no publish; preview only
"""

import argparse
import sys
import traceback

import research_agentic
import research_banking
import terms_agent
import curator_agent
import render_site
import notify

FAILED_STAGES = []


def run_stage(name, fn, critical=False):
    """Run one stage. A critical stage that fails aborts the run immediately."""
    print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
    try:
        fn()
        return True
    except Exception:
        print(f"[{name}] failed:")
        traceback.print_exc()
        FAILED_STAGES.append(name)
        if critical:
            print(f"\n{name} is critical — aborting the rest of the run.")
            finish()
        return False


def finish():
    print(f"\n{'=' * 60}")
    if FAILED_STAGES:
        # Exiting 0 here would paint a partly-broken run green in Actions,
        # which is exactly how a silent failure hides for a month.
        print(f"{len(FAILED_STAGES)} stage(s) FAILED: {', '.join(FAILED_STAGES)}")
        print("=" * 60)
        sys.exit(1)
    print("Run complete — all stages OK.")
    print("=" * 60)
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Run the daily learning pipeline.")
    parser.add_argument("--skip-research", action="store_true",
                        help="Skip both web-research stages (saves API + search credits).")
    parser.add_argument("--no-notify", action="store_true",
                        help="Build and publish, but send no email.")
    parser.add_argument("--local", action="store_true",
                        help="Preview mode: implies --no-notify and skips nothing else.")
    args = parser.parse_args()

    if not args.skip_research:
        run_stage("RESEARCH — Agentic AI teaching material", research_agentic.main)
        run_stage("RESEARCH — AI & automation in banking", research_banking.main)

    run_stage("TERMS — today's glossary lesson", terms_agent.main)

    # From here the stages depend on each other, so a failure stops the chain.
    run_stage("CURATOR — editing the brief", curator_agent.main, critical=True)
    run_stage("SITE — rendering docs/", render_site.main, critical=True)

    if args.no_notify or args.local:
        print("\nEmail skipped (--no-notify).")
    else:
        run_stage("NOTIFY — emailing the brief", notify.main, critical=True)

    finish()


if __name__ == "__main__":
    main()
