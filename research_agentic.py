"""
Research stage 1 — teaching material on Agentic AI.

Tune the brief below to change what shows up. It is the whole editorial
policy for this half of the site.
"""

import research

STAGE = "agentic"

TOPIC_BRIEF = """
TOPIC: teaching material on Agentic AI — material that makes the reader
better at understanding, designing, and evaluating AI agents.

The reader is technically literate and works in enterprise software sales,
not ML research. They can follow an architecture diagram and read code, but
they are not training models. They want to understand how agents actually
work well enough to reason about them honestly in front of customers, and to
build small ones themselves.

In scope:
- How agent loops, tool use, and function calling actually work
- Planning, memory, retrieval, and context management patterns
- Multi-agent orchestration: when it helps, and when it's just latency
- Evaluation: how you tell whether an agent is working, benchmarks and their
  limits, failure modes and how they're detected
- Guardrails, permissioning, human-in-the-loop design
- Concrete build tutorials and reference implementations
- Honest post-mortems of agents that failed in production

Out of scope:
- Prompt-engineering listicles and "10 ChatGPT tricks" content
- Funding rounds, org charts, executive interviews, market-size projections
- Pure model-release news with no explanation of technique
- Vendor content that never gets more specific than "AI-powered"
"""


def main():
    research.run(STAGE, TOPIC_BRIEF)


if __name__ == "__main__":
    main()
