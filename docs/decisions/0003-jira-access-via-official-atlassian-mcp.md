# ADR-0003 — Reach Jira through the official Atlassian MCP server, with API-token auth

- **Status:** Accepted
- **Date:** 2026-10-01
- **Decides:** How the pipeline reads from and writes to Jira.

## Context

The pipeline needs to read a card and, in later steps, move it between statuses.
Jira Cloud is the target; Data Center and Server are not in scope.

A requirement that shaped this more than it first appeared: the eventual pipeline
runs **unattended**. A trigger fires, work happens, a PR appears. Any access
mechanism that depends on a human completing a browser consent flow, or on being
inside an interactive Claude session, fails that requirement — not visibly at first,
but at exactly the moment the thing is supposed to become useful.

MCP was the preferred direction, which initially looked to conflict with unattended
operation, since the widely documented path to the official Atlassian server is
OAuth 2.1 with browser-based 3LO consent. Checking the server documentation rather
than assuming resolved the conflict: the official server also supports API-token
authentication, described as being for "headless, service-style, or non-interactive
client setups". That single fact removed the trade-off this decision appeared to
require, and is the reason the record exists.

## Decision

Use the **official Atlassian MCP server** at `https://mcp.atlassian.com/v2/mcp`
over streamable HTTP, authenticating with a personal API token:

```
Authorization: Basic base64(email:api_token)
```

A service-account API key is also supported as `Authorization: Bearer <api_key>` and
is the better shape for company use (ADR notes below), but a personal token is what
is available in this sandbox.

The same server and the same endpoint are registered in Claude Code via `.mcp.json`,
so interactive exploration and the unattended pipeline talk to one integration
rather than two that can drift apart.

Tool names are **discovered at runtime** via `tools/list` and recorded, not guessed.
The server exposes 46+ tools across several products; writing plausible-looking names
from memory is how a pipeline fails on its first real run.

## Alternatives considered

### Jira REST API directly, with an API token — rejected (reasonable alternative)

The conventional choice, and genuinely defensible. Same credential, no dependency on
an Atlassian-hosted intermediary, stable and exhaustively documented, one less
network hop and no vendor service in the critical path.

It lost because MCP was wanted as the integration style, and because the same server
then serves the model directly in later pipeline steps where a tool interface is more
useful than raw endpoints. Worth recording clearly: **this alternative was not
rejected on merit.** If the MCP server proves unreliable or its latency hurts, REST is
the fallback, and the switch is confined to one adapter module by ADR-0005.

### Community MCP server run locally (`sooperset/mcp-atlassian`) — rejected

Attractive on paper: runs locally in Docker (already installed), takes
`JIRA_URL` / `JIRA_USERNAME` / `JIRA_API_TOKEN` directly, no OAuth, nothing leaves
the machine, which fits "local pipeline" well.

Rejected because the official server covers the same need with first-party support
and no third-party code in the credential path — it already accepts API tokens, which
was the main advantage the local server would have offered. There are also open
reports of stdio transport failures in that project. A dependency that handles
Jira credentials is a poor place to accept avoidable risk.

### Official MCP server with OAuth 2.1 — rejected

The documented default, and the right choice for interactive desktop use. It fails
the unattended requirement: browser-based consent cannot be completed by a trigger
at 03:00, and token refresh becomes state the pipeline has to own and keep valid.

### A model calling MCP tools on the pipeline's behalf (`claude -p` as the Jira client) — rejected

Would have satisfied "use MCP" without a Python MCP client. Rejected on determinism
and cost; see ADR-0005, which generalizes this.

## Consequences

**Good**

- Unattended operation works with a static credential, no browser, no refresh state.
- One integration shared by the pipeline and by Claude Code interactively.
- First-party server: no third-party code sees the Jira credential.
- Later write operations (status transition in Step 5) use the same client and
  credential already proven in Step 1.

**Bad / accepted cost**

- An Atlassian-hosted service sits in the critical path. If it is down or slow, the
  pipeline is. Direct REST would not have this exposure.
- Tool names and response shapes are the server's, not the stable published REST
  contract, and can change under us.
- Jira Cloud only. A company on Data Center cannot use this path at all.
- A personal API token carries the full permissions of a human account — far more
  than the pipeline needs.
- The deprecated `/sse` endpoint is discontinued after 2026-06-30; `/v2/mcp` with
  streamable HTTP is used deliberately to avoid inheriting that.

**Verified 2026-10-01**

- The endpoint and the header *form* are correct. `POST /v2/mcp` with
  `Authorization: Basic base64(email:token)` and a deliberately invalid token
  returns `401 {"error":"invalid_token"}` — the server parsed the header and
  rejected the credential value, rather than rejecting a malformed header.
  Confirmed by `aidlc.jira.mcp_client.probe` against the live server.
- **Correction to an assumption in this ADR:** the Python SDK's
  `streamable_http_client` takes **no `headers` argument**. Custom headers are
  supplied by passing a pre-configured client built with
  `create_mcp_http_client(headers=...)`. Guessing a `headers=` keyword would have
  raised; worse, a plausible-looking wrapper could have connected with no
  `Authorization` header at all and failed confusingly later. Checking the installed
  signature rather than writing from memory is what caught this.
- The protocol client reports transport failures as JSON-RPC `-32603` with **no HTTP
  status attached**, so through it a rejected credential is indistinguishable from a
  server fault. `doctor` therefore probes over plain HTTP first to obtain the real
  status code. This was found by testing the failure path, not by reading docs.

**Verified 2026-10-01, second pass with real credentials**

- A real classic API token authenticates: `HTTP 200`, session initializes,
  **21 tools** listed.
- **A classic API token is not sufficient.** Every tool *call* is refused with
  `Unable to resolve user scopes from the user-context token ... missing the scope
  claim required to authorize this operation (HTTP 401)`. Connecting and listing
  tools succeed; invoking anything does not. Atlassian's own documentation states
  the requirement — *"Scoped token required: Create a personal API token, or ask
  your admin for a service account API key, with the scopes required for the tools
  and data you need to access"* — which this ADR originally recorded as plain
  "API-token authentication" and which was therefore incomplete.
- Scoped tokens are created at id.atlassian.com via **"Create API token with
  scopes"**, a different action from plain "Create API token", and expire between
  1 and 365 days.
- **Tool names, now known** (no longer guesswork): `getJiraIssue`,
  `searchJiraIssuesUsingJql`, `transitionJiraIssue`, `createJiraIssue`,
  `editJiraIssue`, `addOrEditJiraIssueComment`, `atlassianUserInfo`,
  `getAccessibleAtlassianResources`, plus generic `search`, `executeRead`,
  `executeWrite`, `executeDestructive` and Confluence/Loom/Graph tools. The full
  schemas are captured in `.aidlc/tools.json` (gitignored).

  Every stage this pipeline needs has a tool: fetch, search for the trigger,
  transition on completion. That materially de-risks Steps 2 and 5.

**Still unverified**

- That a *scoped* token is accepted for tool calls. This is the open blocker.
- Whether issue descriptions arrive as markdown or as Atlassian Document Format.
- Which specific scopes each tool requires. Atlassian documents that scopes are
  needed but not the per-tool mapping, so this will be established empirically.

## Re-affirmed 2026-10-01, after the REST alternative was shown to work

The scope blocker reopened this decision, because the rejected alternative turned
out to be available immediately while the chosen option was not.

The same classic token that every MCP tool call refuses works against the plain Jira
REST API: `HTTP 200` on `/rest/api/3/myself` and `/rest/api/3/project/search`. So
REST needed no extra setup, no scoped token and carries no expiry, while MCP needed
a new token that expires within a year.

One argument in this ADR also turned out to be weaker than written. "One integration
shared by the pipeline and by Claude Code" is only half true: Claude Code
authenticates to that server over OAuth, while the pipeline uses an API token. The
server is shared; the credential never was. That was not apparent when the decision
was first made.

**Decision unchanged: stay with MCP**, chosen deliberately with the above known. The
tool surface is confirmed to cover every pipeline stage, and the model-facing stages
later benefit from a tool interface. REST remains the fallback, and ADR-0005 keeps
that switch confined to `src/aidlc/jira/mcp_client.py`.

Recorded because a company evaluating this should know that the conventional choice
was available, worked first time, and was passed over on grounds that were about
integration style rather than capability.

## Consequence worth noting

Token expiry is now a real operational concern rather than a theoretical one. A
scoped personal token expires in at most 365 days, so this pipeline will break on a
date certain. That is tolerable in a sandbox and is an argument for the service
account key in a company, alongside the attribution reasons below.

## Portability to a company setting

The server choice is portable; the credential is not.

A personal API token must not be what runs this in a company. It carries one
employee's full Jira permissions, it dies when they leave or rotate it, and every
action the pipeline takes is attributed to them, which destroys the audit trail
precisely where automation makes one most necessary. The company path is the
**service-account API key** (`Authorization: Bearer`), scoped to the projects the
pipeline may touch, with a named owner and a rotation schedule.

Also unresolved for company use: where that credential lives (not a `.env` file on a
developer laptop — a secret manager), and whether Jira Service Management tools are
needed, as the documentation notes those require API-token auth plus explicit admin
enablement.

## References

- [atlassian/atlassian-mcp-server](https://github.com/atlassian/atlassian-mcp-server)
  — endpoints, both auth mechanisms, tool inventory
- [Jira MCP Server Guide 2026](https://mcp.directory/blog/jira-mcp-complete-guide-2026)
  — official vs community comparison
- [sooperset/mcp-atlassian](https://github.com/sooperset/mcp-atlassian) — the
  community server considered above
