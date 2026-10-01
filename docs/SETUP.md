# Setup

Reproduce from zero. Grows as stages are built; right now it covers Step 1 only.

Nothing in this document has been executed yet — Step 1 is scoped but not built
(`docs/PIPELINE.md`). Steps marked **unverified** are written from documentation,
not from having run them.

## Prerequisites

| Tool | Needed for | Verified present on the dev machine |
|---|---|---|
| Python 3.11+ | Pipeline runtime (ADR-0004) | 3.14.5 |
| [uv](https://docs.astral.sh/uv/) | Dependencies, `uv run` entry point | 0.11.30 |
| git | Stages 4–5 | 2.51.0 |
| [gh](https://cli.github.com/) | Stage 5, PR creation | 2.97.0, authenticated as `yurifws` |

`jq` is deliberately not required (ADR-0004).

## 1. Jira access

Three things, in this order. Each one was found by hitting the failure it
prevents, and `aidlc doctor` recognises all three failures. The history is in
ADR-0003.

### 1a. An organization admin enables API-token access to the MCP server

Off by default. Without it, identity calls work but every Jira call is refused
with *"You don't have permission to connect via API token"*.

In [Atlassian Administration](https://admin.atlassian.com): select the
organization → **Rovo** → **Rovo MCP server** → **Authentication** → turn
**API token** on.

> At a company this is a request to an org admin, not something a developer can
> do. Ask for it first; nothing else works without it.

### 1b. Create a token for the MCP server app, with its agent scopes

The MCP server has **its own scope set**, separate from the Jira app's. A
classic token, or a scoped token made for the Jira app, both fail. Open token
creation for the right app directly (link from Atlassian's
[API token guide](https://developer.atlassian.com/cloud/rovo-mcp/guides/configuring-authentication-via-api-token/)):

```
https://id.atlassian.com/manage-profile/security/api-tokens?autofillToken&expiryDays=max&appId=mcp-v2&selectedScopes=all
```

That pre-selects every scope. Keep only what the pipeline uses:

| Scope | Used for |
|---|---|
| `read:jira:agent-interface` | reading a card (Stage 1) |
| `search:jira:agent-interface` | JQL search: the trigger (Stage 2), and `doctor`'s Jira check |
| `write:jira:agent-interface` | subtasks, comments, moving the card to Review (Stages 3, 5) |
| `read:me`, `read:account` | `doctor`'s identity check, which also reports your cloud ID |

Untick every `delete:*` and `manage:*` scope and anything for other products.
The pipeline never deletes or administers anything.

Copy the token immediately; it is shown once. It expires on the date chosen at
creation (at most a year), and the pipeline stops working on that date, so note
it somewhere.

### 1c. Note the account email

The token is not a credential on its own: authentication is
`base64(email:token)`, so `JIRA_EMAIL` must be the account that created it.

> The token still acts as that person, with their project permissions, and
> everything the pipeline does is attributed to them. Acceptable in a sandbox;
> a company should use a service account key instead. See ADR-0003,
> *Portability to a company setting*.

Once `doctor` passes (step 4), **revoke any older tokens** you made along the
way, especially a classic one, which carries every permission your account has.

## 2. Configure

```sh
cp .env.example .env
```

Required: `JIRA_EMAIL`, `JIRA_API_TOKEN`, `AIDLC_PROJECT_KEY`, and
`JIRA_CLOUD_ID` or `JIRA_SITE_URL` (every Jira tool needs one of them; the
server accepts either). Set `JIRA_SITE_URL` anyway: `fetch` uses it to build
the card's link. Every key is documented inline in `.env.example`.

`JIRA_SITE_URL` plays no part in connecting — the pipeline talks to
`https://mcp.atlassian.com/v2/mcp` whatever your site is — but it identifies the
site to each Jira tool and builds links like `{JIRA_SITE_URL}/browse/ABC-123`.

Two things that look like the site URL and are not: `home.atlassian.com/o/...` and
`admin.atlassian.com`. Those are the admin console. Your site URL is what the address
bar shows when Jira itself is open, shaped `https://something.atlassian.net`.
Configuration rejects an admin URL with an explanation rather than letting it fail
later.

`JIRA_CLOUD_ID` appears as the `cloudId` query parameter on those admin URLs, and
`doctor` prints it, so a first `doctor` run without it still tells you the value.

`.env` is gitignored. Do not commit it, and do not paste the token into any
document, commit message or chat.

## 3. Install

```sh
uv sync
```

## 4. Verify the connection

```sh
uv run aidlc doctor
```

Prints the configuration (never the token value), checks the credentials over plain
HTTP, opens an MCP session, calls the identity tools (which report your site and
cloud ID), then runs a one-result JQL search on the configured project — the read
the pipeline actually depends on. The verdict follows that search, not the
connection: identity can work while Jira is blocked.

This is the gate. If it fails, stop here — nothing downstream can work. On failure
it names the cause and the fix; the cases are listed under Troubleshooting.

**Verified 2026-10-01** against the live server, both ways: every failure listed
below was hit and diagnosed, and the success path ends with
*"OK. Connection, 2 identity call(s) and a Jira read succeeded."*

## 5. Discover the server's tools

```sh
uv run aidlc tools
```

Writes the server's `tools/list` output to `.aidlc/tools.json` (gitignored) and
prints a one-line summary per tool. Run once; the real names and argument schemas
inform the fetch implementation. Tool names are not assumed (ADR-0003).

Optional: only needed when the server's tool list changes, or to look up a tool's
arguments.

## 6. Fetch an issue

```sh
uv run aidlc fetch KAN-1
```

Prints the normalized issue as JSON on stdout, and nothing else, so it can be piped
or redirected; diagnostics go to stderr. The shape is documented in
`docs/PIPELINE.md`. Exit code 1 if the card cannot be read.

**Verified 2026-10-01** on KAN-1, and for a missing key (`Issue "KAN-999" not
found (HTTP 404)`).

## 7. Watch the board

Needs `AIDLC_PROJECT_KEY` and the right `AIDLC_TRIGGER_STATUS` (on the sandbox
board, `Development`).

```sh
uv run aidlc detect          # which cards would be picked up; changes nothing
uv run aidlc watch --once    # pick them up, once
uv run aidlc watch           # keep polling until Ctrl-C
```

Picking a card up adds the label `aidlc-claimed` to it in Jira and writes
`.aidlc/runs/<KEY>/issue.json`. To make the pipeline pick a card up again, remove
the label in Jira. Details in `docs/PIPELINE.md`, Step 2.

**Verified 2026-10-01** on KAN-1, including a running loop picking the card up again
after its label was removed.

## Register the same server in Claude Code

So interactive exploration and the unattended pipeline share one integration
(ADR-0003), add `.mcp.json` at the repository root:

```json
{
  "mcpServers": {
    "atlassian": {
      "type": "http",
      "url": "https://mcp.atlassian.com/v2/mcp"
    }
  }
}
```

Claude Code will run an OAuth flow for interactive use, which is fine — it is the
unattended pipeline that needs API-token auth, not the interactive session.

## Running the tests

```sh
uv run pytest
```

No network. Covers configuration, `doctor`'s diagnosis of each server refusal
(using the server's real messages), and normalization of a real `getJiraIssue`
response captured as a fixture. The live interaction itself is verified by
`doctor` and `fetch` against the real server, because a mock would only confirm
assumptions that had not been checked.

## Troubleshooting

`doctor` recognises each of these and prints the fix. They are listed in the order
they were hit while setting up the sandbox.

### Every tool call REFUSED: *"missing the scope claim"* (HTTP 401)

A classic API token. It authenticates and lists tools but can call none of them.
Create the token as in step 1b.

### REFUSED: *"Insufficient scopes ... Required: [...]"* (HTTP 403)

A scoped token missing the named scopes. Most often, a token made for the **Jira
app** rather than the **MCP server app**: the server uses its own
`*:agent-interface` scopes. Create a new token with the step 1b link, which opens
the right app.

### Identity works, Jira REFUSED: *"You don't have permission to connect via API token"*

API-token access to the MCP server is off for the organization. An org admin turns
it on: step 1a.

### `detect` finds nothing, but a card is in the column

In order of likelihood: the card already carries `aidlc-claimed` (remove it to
re-run); `AIDLC_TRIGGER_STATUS` does not match the status name exactly (it is the
status, not the column title, and the two can differ); `AIDLC_PROJECT_KEY` points at
another project. `detect` prints the exact query it ran, so paste it into Jira's
issue search to see what Jira makes of it.

### `doctor` reports HTTP 401 `invalid_token`

The header reached the server and the credential was rejected. In order of
likelihood: the email and token belong to different accounts; the token was revoked
or rotated; the token was copied with surrounding whitespace or truncated.

### An error mentioning `TaskGroup` with no detail

The MCP SDK wraps failures in nested task groups. The CLI flattens these before
printing, so if you see a bare `unhandled errors in a TaskGroup` message it came from
somewhere outside the CLI. Run `doctor`, which reports the HTTP status directly.
