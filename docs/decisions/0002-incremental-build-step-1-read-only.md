# ADR-0002 — Build incrementally; Step 1 is a read-only Jira trigger

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** How the pipeline is sequenced, and what the first step delivers.

## Context

The end goal has five distinct stages: detect a card entering "In development",
break it into subtasks, implement subtask by subtask on one branch, open a PR, move
the card to "In review". Each stage has a different failure mode. Jira integration
fails on credentials and field formats. Subtask breakdown fails on judgement
quality. Implementation fails on code correctness. PR creation fails on git and
GitHub state. Status transition fails on workflow permissions and transition IDs.

Built together, a failure anywhere surfaces as "the pipeline did not work", and the
stages are not independently observable enough to tell which part lied.

The repository was empty when this was decided — no commits, no structure to
accommodate.

## Decision

Build one stage at a time. Each stage must be independently runnable and verified
against real Jira data before the next begins.

**Step 1, agreed scope:** authenticate to Jira, fetch one issue by key, emit it as
normalized JSON. Nothing else — no subtask breakdown, no git operations, no code
generation, no PR, no status transition, no trigger detection.

Step 1 is invoked manually with an issue key. The fetch layer is shaped so a trigger
can call it later (ADR-0006), but no trigger is built now.

The current step is tracked in `docs/PIPELINE.md`. Work does not run ahead of it.

## Alternatives considered

### Trigger plus subtask breakdown in one step — rejected

Doubles the surface of the first step and puts two unlike failure modes in one
debugging session: credential and field-format problems, which are factual and have
one right answer, alongside breakdown quality, which is a judgement call with no
test that settles it. Bad output would have been ambiguous between "Jira gave us a
poor description" and "the prompt is weak".

### Full skeleton with every stage stubbed — rejected

Produces the shape early, which is genuinely attractive, but nothing works and the
riskiest unknown — whether credentials and data formats cooperate at all — stays
unproven behind five layers of logging. It also fixes the interfaces between stages
before anything is known about what flows across them.

### Mock Jira first, real Jira later — rejected

Fastest route to a passing test and the least informative. Every surprise met so
far came from the real service: which authentication mechanisms the MCP server
accepts, what its tools are actually named, and whether descriptions arrive as text
or Atlassian Document Format. A fixture would have confirmed only that the code
matches assumptions nobody had checked.

Fixtures are still used — captured from real responses, after the fact, to test
normalization offline.

## Consequences

**Good**

- Each failure is attributable to one stage.
- The hardest-to-fake part — real credentials, real card data — is proven first.
- A step that turns out to be wrong is cheap to discard.

**Bad / accepted cost**

- Interfaces between stages emerge late, so some early shapes will need reworking
  once later stages reveal what they need.
- Slower to a visible end-to-end demo. There is nothing impressive to show after
  Step 1 beyond a JSON blob, which is a real cost when the audience is a team being
  asked to adopt this.

**Unverified at time of writing**

- Step 1 has not been run. No credential path, tool name or data format has been
  confirmed against the live service.

## Portability to a company setting

The sequencing is portable and advisable. The specific scope boundary is not
load-bearing: a company adopting this would likely also start from Step 1, but
against a sandbox Jira project rather than a live board, and would need a decision
this ADR does not make about which project and which service account the pipeline
is permitted to act on.
