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
2. Create a personal API token at
   [id.atlassian.com → Security → API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
   Copy it immediately; it is shown once.
3. Note your Atlassian account email. The token is not a credential on its own —
   authentication is `base64(email:token)` (ADR-0003).

> A personal token carries that account's full Jira permissions. Acceptable in a
> sandbox, not acceptable in a company — see ADR-0003, *Portability to a company
> setting*.

## 2. Configure

```sh
cp .env.example .env
```

Fill in `JIRA_SITE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and `AIDLC_PROJECT_KEY`.
Each key is documented inline in `.env.example`.

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

Expected: your Atlassian account and the accessible site's cloud ID. This is the
gate — if it fails, stop here. Nothing downstream can work and a failure at this
point is almost always one of: wrong email/token pairing, a token that was rotated,
or a site URL with a trailing slash.

**Unverified.** Not yet run against the live server.

## 5. Discover the server's tools

```sh
uv run aidlc tools
```

Writes the server's `tools/list` output to `.aidlc/tools.json` (gitignored). Run
once; the real tool names and argument schemas inform the fetch implementation. Tool
names are not assumed (ADR-0003).

**Unverified.**

## 6. Fetch an issue

```sh
uv run aidlc fetch SCRUM-1
```

Prints normalized issue JSON. Shape is provisional — see `docs/PIPELINE.md`.

**Unverified.**

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

## Troubleshooting

Empty until there is something real to record. Problems actually encountered get
written down here when they happen, not invented in advance.
