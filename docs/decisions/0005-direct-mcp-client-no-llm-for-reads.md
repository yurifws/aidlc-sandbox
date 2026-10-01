# ADR-0005 — The pipeline is a direct MCP client; no model in deterministic paths

- **Status:** Accepted — see *Status note* for how
- **Date:** 2026-10-01
- **Decides:** Where the boundary falls between deterministic code and model judgement.

## Context

Choosing MCP for Jira access (ADR-0003) raised a question that is easy to miss,
because MCP is usually encountered as something a model uses. Two arrangements both
satisfy "the pipeline uses MCP":

1. **Model as client.** The pipeline invokes `claude -p` with the Atlassian MCP
   server available and asks, in prose, for the issue. The model calls the tool and
   returns the data.
2. **Pipeline as client.** The Python process speaks MCP itself over streamable HTTP
   and calls the tool directly. No model involved.

MCP is a protocol, not a model feature — a JSON-RPC interface with typed tools.
Nothing about it requires an LLM. The first arrangement is nonetheless the more
intuitive one, and worth rejecting explicitly rather than by omission.

This generalizes past Jira. The full pipeline mixes operations that have one correct
answer (fetch an issue, create a branch, open a PR, transition a card) with
operations that require judgement (break a card into subtasks, write the
implementation, describe the change). Those two kinds deserve different machinery.

## Decision

Deterministic operations are performed by code. The pipeline is itself an MCP client,
connecting to the Atlassian server directly and calling tools by name with typed
arguments.

A model is invoked only where the task is genuinely a judgement call: subtask
breakdown, implementation, PR description.

The MCP interaction lives behind one adapter module exposing a narrow interface
(`fetch_issue`, later `search`, `transition`). Nothing outside that module knows the
transport, the auth header or the server's tool names.

Stated as a rule for the rest of the build: **code watches and executes, the model
thinks.**

## Alternatives considered

### Model as MCP client for everything — rejected

Simplest to write and the most natural reading of "use MCP". Rejected on four counts,
in descending order of weight:

- **Non-determinism where it is not wanted.** Fetching issue `ABC-123` has exactly
  one right answer. Routing it through a sampled generation introduces variance into
  a step that has no use for variance — paraphrased summaries, dropped fields,
  occasionally a confidently invented field value. Field-level fidelity matters here:
  the issue description is the input to every later stage.
- **Cost and latency per run.** A token-billed inference call and several seconds of
  latency, repeated on every poll tick and every pipeline stage, to do work a direct
  RPC does in milliseconds for nothing.
- **Unfalsifiable failures.** When a direct tool call fails it returns an error with
  a status code. When a model mediates, failure can arrive as plausible prose, which
  is strictly worse than an exception.
- **Error handling has nowhere to live.** Retries, rate limits and auth expiry are
  handled properly against a protocol client and only approximately against a prose
  interface.

### Model as client for reads, code for writes — rejected

No coherent principle. Reads are the *more* fidelity-sensitive direction, since their
output feeds every later stage. If anything the split would want to be the other way,
which is an argument that the split is wrong rather than inverted.

### Pipeline uses REST, model uses MCP separately — rejected

Two independent Jira integrations with two credential paths that can drift out of
agreement. ADR-0003 chose one integration shared by both deliberately.

## Consequences

**Good**

- Deterministic stages are reproducible, fast, free, and fail loudly.
- Model cost is spent only where judgement is actually required.
- Swapping MCP for REST, should ADR-0003 prove wrong, touches one module.
- Each stage can be tested in isolation: deterministic stages against fixtures, model
  stages by inspecting their output.

**Bad / accepted cost**

- More code than asking a model in prose. Tool schemas must be read and arguments
  constructed correctly.
- The pipeline must handle MCP protocol concerns itself: session setup, errors,
  reconnection.
- Tool-name and schema changes on the server break the pipeline directly, where a
  model would often adapt. This is a real loss of resilience, accepted in exchange
  for failing loudly instead of silently.

**Unverified at time of writing**

- No MCP connection has been established yet from Python, by either arrangement.

## Status note

Accepted **by delegation**, not by agreement with the reasoning above. It was written
up as Proposed, and implementation was authorised in general terms ("as you need")
without the argument being separately examined. Recorded this way because the
distinction matters: no one has yet pushed back on this, and it is the most
consequential decision in the set — it fixes where model judgement is permitted for
every later stage.

It is cheap to reverse. The MCP interaction is confined to
`src/aidlc/jira/mcp_client.py`, so moving the boundary, or swapping the transport for
REST, touches one module. If this reasoning is wrong, it should be superseded rather
than left standing on the strength of nobody having objected.

## Portability to a company setting

The most portable decision in the set, and the one most worth carrying over intact.
The boundary between "deterministic enough to be code" and "needs judgement" is what
makes an AI pipeline auditable: the deterministic stages can be reasoned about and
tested normally, and review attention concentrates on the few places a model
actually decided something.

A company would likely draw the line in the same place but tighten it further, for
instance requiring human approval on the model-authored stages before a PR is opened.
