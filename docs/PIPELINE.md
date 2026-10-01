# Pipeline stages and current progress

Each stage is built, run against real data, and verified before the next begins
(ADR-0002). This file records where the build actually is — not where it is
intended to end up.

## Current state

**Step 1 — in progress on `feat/step-1-jira-fetch`.**

| Piece | State |
|---|---|
| `aidlc doctor` | Built and run against real Jira. Correctly reports the current blocker |
| `aidlc tools` | Built and run. 21 tools captured to `.aidlc/tools.json` |
| `aidlc fetch KEY` | **Not implemented.** Tool name is now known (`getJiraIssue`); blocked on authorization |
| Normalization + fixture test | Not started. Needs a real response to capture |

**Blocked on a scoped API token.** A classic token connects and lists tools but
cannot call any of them. See ADR-0003 and `docs/SETUP.md` step 1.

`fetch` is deliberately absent rather than stubbed. The tool name is now known, but
its argument schema cannot be exercised and the response shape is unknown until a
call actually succeeds — and normalization is mostly a function of that shape.

**Next action is yours:** create a scoped API token, replace `JIRA_API_TOKEN` in
`.env`, and re-run `uv run aidlc doctor`.

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

- ~~**Tool names.**~~ **Resolved.** 21 tools, read from `tools/list`. The ones this
  pipeline needs: `getJiraIssue` (Stage 1), `searchJiraIssuesUsingJql` (Stage 2),
  `transitionJiraIssue` (Stage 5). Every stage has a tool, which de-risks the rest
  of the build.
- **Description format.** Jira Cloud stores descriptions as Atlassian Document
  Format, a nested JSON structure, not plain text. Whether the MCP server flattens
  this to markdown or passes ADF through is unknown. If it is ADF, normalization
  needs a flattener, and that will be flagged rather than silently mangled.
- **Acceptance criteria.** Often a custom field (`customfield_NNNNN`) rather than
  part of the description, and the field ID is instance-specific. May not exist on
  this board at all.
- ~~**Header handling.**~~ **Resolved.** Headers go via
  `create_mcp_http_client(headers=...)`; `streamable_http_client` has no `headers`
  argument. See ADR-0003.
- **Authorization.** A classic API token lists tools but cannot call them. Needs a
  scoped token. This is the current blocker.

### Done when

`uv run aidlc fetch <a real key>` prints correct JSON for a real card on the real
board, and a fixture captured from that response has an offline test covering
normalization.
