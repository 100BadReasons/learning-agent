"""
Research stage 2 — AI and automation in the banking industry.

Tune the brief below to change what shows up.
"""

import research

STAGE = "banking"

TOPIC_BRIEF = """
TOPIC: technology enhancements in AI and automation in the banking industry —
what banks and financial institutions are actually deploying, what's
constraining them, and what's changing.

The reader sells enterprise software into financial services. They need to
walk into a bank conversation knowing what that bank's peers are actually
doing, what the regulators are actually saying, and where the real friction
is. Substance over press release.

In scope:
- Named deployments at named institutions, with enough detail to be credible:
  what was automated, on what stack, with what result
- Regulatory movement that shapes what banks can deploy: DORA, EU AI Act,
  OCC/FRB/FCA guidance, model risk management (SR 11-7 and successors)
- Core banking modernization, payments automation, fraud and AML detection,
  KYC/onboarding, credit decisioning, claims and servicing workflows
- Legacy-estate reality: mainframe integration, COBOL, data residency, and
  why bank AI projects stall
- Vendor and platform moves that genuinely change what's buildable
- Skeptical, evidence-based coverage of results that did not materialize

Out of scope:
- Consultancy reports whose only content is a market-size number
- "AI will transform banking" think pieces with no named institution in them
- Retail crypto and consumer fintech app news
- Earnings coverage where AI is one line in a CFO's remarks
"""


def main():
    research.run(STAGE, TOPIC_BRIEF)


if __name__ == "__main__":
    main()
