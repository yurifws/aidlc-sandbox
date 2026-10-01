# aidlc-sandbox

A local AI-DLC pipeline connecting Jira to this repository.

**Goal:** a Jira card moving to *In development* is broken into subtasks,
implemented subtask by subtask on one branch, a PR is opened, and the card moves to
*In review*.

**Status:** Step 1 of 5 scoped and documented. No code written yet. Nothing verified
against live Jira.

## Why the documentation is heavy

This is a prototype intended for adoption inside a company. The deliverable is not
just working code — it is a set of choices a colleague can evaluate, challenge and
reproduce without the author present. So every decision that could reasonably have
gone another way is written down as it is made, with the rejected alternatives and
the reasons they lost.

That rule is itself a decision: [ADR-0001](docs/decisions/0001-document-every-decision.md).

## Reading order

| Document | What it tells you |
|---|---|
| [`docs/PIPELINE.md`](docs/PIPELINE.md) | The five stages, and where the build actually is |
| [`docs/decisions/`](docs/decisions/README.md) | Why it is built this way, and what was rejected |
| [`docs/SETUP.md`](docs/SETUP.md) | Reproduce from zero |
| [`CLAUDE.md`](CLAUDE.md) | The working agreement this repository is built under |

## Decisions so far

| # | Decision | Status |
|---|---|---|
| [0001](docs/decisions/0001-document-every-decision.md) | Document every decision as it is made | Accepted |
| [0002](docs/decisions/0002-incremental-build-step-1-read-only.md) | Build incrementally; Step 1 is a read-only Jira trigger | Accepted |
| [0003](docs/decisions/0003-jira-access-via-official-atlassian-mcp.md) | Reach Jira through the official Atlassian MCP server, API-token auth | Accepted |
| [0004](docs/decisions/0004-python-uv-runtime.md) | Python + uv as the pipeline runtime | Accepted |
| [0005](docs/decisions/0005-direct-mcp-client-no-llm-for-reads.md) | Pipeline is a direct MCP client; no model in deterministic paths | Accepted (by delegation) |
| [0006](docs/decisions/0006-trigger-mechanism.md) | Trigger by deterministic poller, not a watching agent | **Deferred** |
| [0007](docs/decisions/0007-conventional-commits-one-per-unit-of-work.md) | Conventional Commits, one commit per unit of work | Accepted |
| [0008](docs/decisions/0008-diagrams-in-documentation.md) | Use Mermaid diagrams where structure is the point | Accepted |

## The shape of it

The pipeline mixes operations that have one correct answer with operations that
require judgement, and treats them differently — code watches and executes, the
model thinks ([ADR-0005](docs/decisions/0005-direct-mcp-client-no-llm-for-reads.md)).
That boundary is what makes the thing auditable: deterministic stages can be tested
normally, and review attention concentrates on the few places a model actually
decided something.

## Getting started

See [`docs/SETUP.md`](docs/SETUP.md). Short version: Python 3.11+, `uv`, a Jira
Cloud API token, `cp .env.example .env`, fill it in.
