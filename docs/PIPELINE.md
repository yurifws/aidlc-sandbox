# Pipeline stages and current progress

Each stage is built, run against real data, and verified before the next begins
(ADR-0002). This file records where the build actually is — not where it is
intended to end up.

## Current state

**Step 1 — in progress on `feat/step-1-jira-fetch`.**

| Piece | State |
|---|---|
| `aidlc doctor` | Built. Config validation and the 401 path verified; success path needs real credentials |
| `aidlc tools` | Built. Not yet run — blocked on working credentials |
| `aidlc fetch KEY` | **Not implemented.** Blocked on `tools` output; tool names are not guessed (ADR-0003) |
| Normalization + fixture test | Not started. Needs a real response to capture |

`fetch` is deliberately absent rather than stubbed: its implementation depends on
tool names and on whether descriptions arrive as markdown or ADF, neither of which
is known yet.

**Next action is yours:** fill in `.env` and run `uv run aidlc doctor`.

## Stages

| # | Stage | Decides / emits | Machinery | Status |
|---|---|---|---|---|
| 1 | **Fetch** | Issue key in, normalized issue JSON out | Code (ADR-0005) | Scoped, not built |
| 2 | **Detect** | Card entered trigger status, hands off issue key | Code, poller (ADR-0006) | Not started |
| 3 | **Break down** | Issue JSON in, ordered subtask plan out | Model | Not started |
| 4 | **Implement** | One subtask at a time, one commit each, on one branch | Model | Not started |
| 5 | **Publish** | Branch pushed, PR opened, card moved to review status | Code | Not started |

The split between code and model stages is deliberate and is the subject of
ADR-0005: code watches and executes, the model thinks.

Stage 4 writes commits unattended, so the commit convention (ADR-0007) is an output
contract of this pipeline rather than developer hygiene: one subtask, one
Conventional Commit, body explaining why. That history is the only record a reviewer
has of how the work was sequenced, and Stage 5 derives the PR description from it.
Commit quality therefore depends on breakdown quality in Stage 3.

## Step 1 — scope as agreed

**In scope:** authenticate to the Atlassian MCP server, fetch one issue by key,
normalize it, print it as JSON.

**Out of scope:** everything in stages 2–5. No git operations, no code generation,
no PR, no status transition, no trigger.

### Planned commands

| Command | Purpose |
|---|---|
| `uv run aidlc doctor` | Connect and confirm credentials work. The gate — nothing else matters until this passes. |
| `uv run aidlc tools` | Dump the server's `tools/list` to a scratch file. Discovery, not guesswork (ADR-0003). |
| `uv run aidlc fetch KEY` | Fetch one issue, emit normalized JSON. |

### Planned output shape

Provisional — the real field set depends on what the server returns, which is
unverified:

```json
{
  "key": "SCRUM-1",
  "summary": "...",
  "description": "...",
  "acceptance_criteria": "...",
  "status": "In development",
  "issue_type": "Story",
  "labels": [],
  "url": "https://acme.atlassian.net/browse/SCRUM-1"
}
```

### Known unknowns

Recorded because they are the likeliest source of surprise, per ADR-0003:

- **Tool names.** The server exposes 46+ tools. Names will be read from
  `tools/list`, not assumed.
- **Description format.** Jira Cloud stores descriptions as Atlassian Document
  Format, a nested JSON structure, not plain text. Whether the MCP server flattens
  this to markdown or passes ADF through is unknown. If it is ADF, normalization
  needs a flattener, and that will be flagged rather than silently mangled.
- **Acceptance criteria.** Often a custom field (`customfield_NNNNN`) rather than
  part of the description, and the field ID is instance-specific. May not exist on
  this board at all.
- **Header handling.** Whether the Python MCP SDK passes a custom `Authorization`
  header cleanly over streamable HTTP. Expected to; not yet run.

### Done when

`uv run aidlc fetch <a real key>` prints correct JSON for a real card on the real
board, and a fixture captured from that response has an offline test covering
normalization.
