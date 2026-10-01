# Decision records

Numbered, immutable, append-only. One decision per file, named `NNNN-slug.md`.

Written for someone who was not in the room — most likely a colleague evaluating
whether to adopt this pipeline. They arrive asking "why not the obvious thing?", so
every record answers that before it describes what was built.

## Status values

| Status | Meaning |
|---|---|
| `Proposed` | Written up, not yet agreed. Do not build on it. |
| `Accepted` | Agreed. In force. |
| `Deferred` | Deliberately not decided yet. Names the trigger that revisits it. |
| `Superseded by ADR-NNNN` | Replaced. Body left intact as evidence. |

## Changing a decision

Write a new ADR. Set the old status to `Superseded by ADR-NNNN`. Never edit the
reasoning of a decided record — the wrong turns are the useful part of a log like
this.

## Portability

This is a local, single-user sandbox. Some decisions were made *because* of that and
will not survive contact with a company environment: shared credentials, concurrent
runs, CI, audit, multiple repos. Each record flags these under **Portability to a
company setting** so a reader can tell which conclusions transfer and which were
sandbox convenience.

## Index

| # | Decision | Status |
|---|---|---|
| [0001](0001-document-every-decision.md) | Document every decision | Accepted |
| [0002](0002-incremental-build-step-1-read-only.md) | Build incrementally; Step 1 is a read-only Jira trigger | Accepted |
| [0003](0003-jira-access-via-official-atlassian-mcp.md) | Reach Jira through the official Atlassian MCP server, API-token auth | Accepted |
| [0004](0004-python-uv-runtime.md) | Python + uv as the pipeline runtime | Accepted |
| [0005](0005-direct-mcp-client-no-llm-for-reads.md) | Pipeline is a direct MCP client; no LLM in deterministic paths | Accepted (by delegation) |
| [0006](0006-trigger-mechanism.md) | Trigger by deterministic poller, not a watching agent | Deferred |
| [0007](0007-conventional-commits-one-per-unit-of-work.md) | Conventional Commits, one commit per unit of work | Accepted |
