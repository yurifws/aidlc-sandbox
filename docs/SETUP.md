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

## 1. Jira credentials

1. Sign in to the Jira Cloud site the pipeline will act on.
2. Create a **scoped** API token at
   [id.atlassian.com → Security → API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
   Choose **"Create API token with scopes"** — not plain "Create API token".
   Select the Jira app and grant at least read access to Jira work; write and
   transition scopes are needed later, for pipeline Steps 4–5.
   Copy it immediately; it is shown once.

   **A classic unscoped token does not work.** It authenticates, and the server
   lists all 21 tools, but every tool *call* is refused with "missing the scope
   claim". Verified against the live server — see ADR-0003. If you already created
   a classic token, create a scoped one and replace it.

   Scoped tokens expire between 1 and 365 days. Note the expiry: this pipeline
   will stop working on a date certain.
3. Note your Atlassian account email. The token is not a credential on its own —
   authentication is `base64(email:token)` (ADR-0003).

> A personal token carries that account's full Jira permissions. Acceptable in a
> sandbox, not acceptable in a company — see ADR-0003, *Portability to a company
> setting*.

## 2. Configure

```sh
cp .env.example .env
```

Only two values are required: `JIRA_EMAIL` and `JIRA_API_TOKEN`. Every key is
documented inline in `.env.example`.

`JIRA_SITE_URL` is optional and plays no part in connecting — the pipeline talks to
`https://mcp.atlassian.com/v2/mcp` whatever your site is. It exists only to build
human-facing links like `{JIRA_SITE_URL}/browse/ABC-123`.

Two things that look like the site URL and are not: `home.atlassian.com/o/...` and
`admin.atlassian.com`. Those are the admin console. Your site URL is what the address
bar shows when Jira itself is open, shaped `https://something.atlassian.net`.
Configuration rejects an admin URL with an explanation rather than letting it fail
later.

`JIRA_CLOUD_ID` is also optional. It appears as the `cloudId` query parameter on
those admin URLs, and `doctor` reports the cloud IDs your credentials can reach.

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
HTTP, then opens an MCP session and reports how many tools the server exposes plus
which of them look like identity or issue tools.

This is the gate. If it fails, stop here — nothing downstream can work.

On failure it reports the real HTTP status and the likely cause. A 401 is almost
always one of: `JIRA_EMAIL` and `JIRA_API_TOKEN` belonging to different accounts, a
rotated token, or whitespace picked up while copying.

**Partly verified.** The failure path is confirmed against the live server: an
invalid token returns `401 {"error":"invalid_token"}` and `doctor` reports it
correctly. The success path has not been run, because that needs real credentials.

## 5. Discover the server's tools

```sh
uv run aidlc tools
```

Writes the server's `tools/list` output to `.aidlc/tools.json` (gitignored) and
prints a one-line summary per tool. Run once; the real names and argument schemas
inform the fetch implementation. Tool names are not assumed (ADR-0003).

**Unverified.** Needs working credentials.

## 6. Fetch an issue

**Not implemented yet.** It is blocked on step 5: the fetch call needs the real tool
name and argument schema, and normalization depends on whether descriptions arrive as
markdown or as Atlassian Document Format. Writing it before `tools` has run would
mean guessing both.

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

Covers configuration loading and validation only — no network. The MCP interaction is
verified by `aidlc doctor` against the real server instead, because mocking it would
only confirm assumptions that had not been checked.

## Troubleshooting

### `doctor` connects and lists tools, but every tool call is REFUSED

The message mentions a missing scope claim. Your token is a classic unscoped API
token. Create a scoped one — see step 1. This is the single most likely thing to go
wrong in setup, because the Atlassian UI offers the classic token first.

### `doctor` reports HTTP 401 `invalid_token`

The header reached the server and the credential was rejected. In order of
likelihood: the email and token belong to different accounts; the token was revoked
or rotated; the token was copied with surrounding whitespace or truncated.

### An error mentioning `TaskGroup` with no detail

The MCP SDK wraps failures in nested task groups. The CLI flattens these before
printing, so if you see a bare `unhandled errors in a TaskGroup` message it came from
somewhere outside the CLI. Run `doctor`, which reports the HTTP status directly.
