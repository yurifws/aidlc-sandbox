"""Command line entry point.

argparse rather than click/typer: three subcommands do not justify a dependency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from aidlc import config as config_mod
from aidlc.config import REPO_ROOT, Config, ConfigError
from aidlc.jira import mcp_client

OUT_DIR = REPO_ROOT / ".aidlc"

# Substrings that suggest a tool is about identity or issue retrieval. Used only
# to make `doctor` output useful; nothing dispatches on these.
IDENTITY_HINTS = ("userinfo", "accessible", "resources", "whoami")
ISSUE_HINTS = ("issue", "jql", "search")


def _render(result: object, limit: int = 1200) -> str:
    """Flatten an MCP tool result to text for display.

    Content blocks are typed (text, image, resource); only text is useful in a
    terminal diagnostic, so anything else is named rather than dumped.
    """
    blocks = getattr(result, "content", None) or []
    parts: list[str] = []
    for block in blocks:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else f"<{getattr(block, 'type', 'unknown')} block>")
    rendered = "\n".join(parts).strip() or "(empty result)"
    return rendered if len(rendered) <= limit else rendered[:limit] + "\n... (truncated)"


def _tool_error(result: object) -> str | None:
    """Return an error description if a tool call failed, else None.

    A failed tool call does not raise. MCP can report failure two ways, and the
    Atlassian server uses the second: `isError` may be false while the content is
    a JSON body carrying `"error": true` and an HTTP status. Checking only
    `isError` makes a wall of 401s look like success, which is worse than an
    outright crash because it gets reported as working.
    """
    text = _render(result, limit=4000)

    # Parse before consulting is_error: a JSON body gives a readable message,
    # where the raw render is a wall of escaped JSON.
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        payload = None

    if isinstance(payload, dict) and payload.get("error"):
        status = payload.get("statusCode")
        message = payload.get("message") or "unspecified error"
        return message + (f" (HTTP {status})" if status else "")

    if getattr(result, "is_error", False):
        return text[:400]
    return None


CLASSIC_TOKEN_DIAGNOSIS = """Every tool call was rejected for a missing scope claim, although the
connection and tool listing succeeded.

This is what a CLASSIC API token looks like against this server. A classic token
authenticates but carries no scopes, so tools/list works while every tool call
is refused.

Fix: create a SCOPED token instead.
  1. https://id.atlassian.com/manage-profile/security/api-tokens
  2. choose "Create API token with scopes", NOT plain "Create API token"
  3. select the Jira app, and grant at least read access to Jira work
     (write and transition scopes are needed later, for pipeline Steps 4-5)
  4. replace JIRA_API_TOKEN in .env and re-run this command

Scoped tokens expire between 1 and 365 days, so this will need rotating -- one
more reason a company deployment wants a service account key (ADR-0003)."""

# The server names what it wanted, e.g. 'Insufficient scopes ... Required: [read:me]'.
REQUIRED_SCOPES = re.compile(r"Required:\s*\[([^\]]*)\]")


def _missing_scopes_diagnosis(scopes: set[str]) -> str:
    """For a scoped token that lacks specific scopes.

    Distinct from the classic-token case: here the token carries scopes, just not
    the ones asked for, and the server says exactly which. Telling the user to
    make a scoped token -- the classic-token advice -- would send them in a loop.
    """
    listed = "\n".join(f"  - {s}" for s in sorted(scopes))
    return (
        "The token is scoped, but lacks scopes the server asked for:\n"
        f"{listed}\n\n"
        "Scopes are chosen when a token is created, so the usual fix is a new\n"
        "scoped token that includes these as well as the Jira scopes. Replace\n"
        "JIRA_API_TOKEN in .env and re-run this command.\n\n"
        "These are account-level scopes, not Jira ones. If the token screen does not\n"
        "offer them, record that: it would mean a personal scoped token cannot drive\n"
        "this MCP server, which reopens ADR-0003."
    )


def _status_diagnosis(status: int, body: str) -> str:
    if status == 401:
        return (
            f"The server rejected the credentials (401: {body.strip()}).\n"
            "Most likely causes, in order:\n"
            "  - JIRA_EMAIL and JIRA_API_TOKEN belong to different accounts\n"
            "  - the token was revoked, expired, or copied with stray whitespace\n"
            "  - the token was pasted only partially"
        )
    if status == 403:
        return (
            f"Authenticated but not authorized (403: {body.strip()}).\n"
            "The account may lack access to the site, or API-token access may need\n"
            "admin enablement for this instance."
        )
    return f"Unexpected HTTP {status} from the MCP endpoint:\n{body}"


async def _doctor(config: Config) -> int:
    print("Configuration")
    for key, value in config.describe().items():
        print(f"  {key:14} {value}")

    # Ask over plain HTTP first. The protocol client reports every failure as
    # JSON-RPC -32603 with no status code, so a bad token and a server fault are
    # indistinguishable through it.
    print(f"\nChecking credentials against {config.mcp_endpoint} ...")
    status, body = await mcp_client.probe(config)
    if status >= 400:
        # Report on stdout, not stderr: doctor's output is a diagnostic report and
        # must read in order. The exit code carries the verdict.
        print(f"  HTTP {status}\n")
        print(_status_diagnosis(status, body))
        return 1
    print(f"  HTTP {status}, credentials accepted")

    print("\nOpening MCP session ...")
    async with mcp_client.connect(config) as session:
        tools = list((await session.list_tools()).tools)
        print(f"  session initialized, {len(tools)} tools available")

        identity = [t for t in tools if any(h in t.name.lower() for h in IDENTITY_HINTS)]
        issue = [t.name for t in tools if any(h in t.name.lower() for h in ISSUE_HINTS)]

        # Call the identity tools that need no arguments. This is what tells you
        # your site URL and cloud ID, which are otherwise a hunt through the
        # Atlassian admin console. Tools with required arguments are skipped
        # rather than called with guesses.
        print("\nWho am I, and what can I reach?")
        attempted = 0
        succeeded = 0
        no_scope_claim = 0
        missing_scopes: set[str] = set()
        for tool in identity:
            # `input_schema` is the Python attribute; `inputSchema` is only its
            # serialization alias. Using the wire name raises AttributeError.
            if (tool.input_schema or {}).get("required"):
                print(f"  {tool.name}: skipped, needs arguments")
                continue
            attempted += 1
            try:
                result = await session.call_tool(tool.name, {})
            except Exception as err:  # noqa: BLE001 - diagnostic, keep going
                print(f"  {tool.name}: call raised {type(err).__name__}: {err}")
                continue

            error = _tool_error(result)
            if error:
                print(f"  {tool.name}: REFUSED - {error}")
                # Two different scope failures with two different fixes: a token
                # with no scopes at all (classic), and a scoped token missing
                # specific ones. Matching on "scope" alone conflated them.
                if "missing the scope claim" in error:
                    no_scope_claim += 1
                if match := REQUIRED_SCOPES.search(error):
                    missing_scopes.update(
                        s.strip() for s in match.group(1).split(",") if s.strip()
                    )
                continue
            succeeded += 1
            print(f"  {tool.name}:")
            for line in _render(result).splitlines():
                print(f"    {line}")
        if not identity:
            print("  (no identity tools matched; see `aidlc tools` for the full list)")

        print("\nCandidate issue tools:")
        print("\n".join(f"  {n}" for n in issue) or "  (none matched)")

        # Identity tools passing does not mean Jira is readable: an org-level
        # setting can block Jira tools for API tokens while identity tools still
        # work. Observed, not hypothetical -- doctor once reported OK in exactly
        # that state. So test the read the pipeline actually depends on.
        jira_error = await _check_jira_read(session, config)

    # The verdict must reflect tool CALLS, not merely connecting. Listing tools
    # succeeds with a credential that cannot invoke any of them, so reporting
    # success on connection alone would be a false pass.
    if attempted and not succeeded:
        print()
        if no_scope_claim:
            print(CLASSIC_TOKEN_DIAGNOSIS)
        elif missing_scopes:
            print(_missing_scopes_diagnosis(missing_scopes))
        else:
            print("Every tool call was refused. See above.")
        return 1

    if not attempted:
        print("\nConnected, but no identity tool was callable without arguments, so")
        print("whether tool calls are authorized is UNVERIFIED. See `aidlc tools`.")
        return 1

    if jira_error:
        print()
        print(jira_error)
        return 1

    print(f"\nOK. Connection, {succeeded} identity call(s) and a Jira read succeeded.")
    return 0


API_TOKEN_DISABLED_DIAGNOSIS = """Identity tools work, but every Jira tool is refused: API-token access to the
Atlassian Rovo MCP server is switched off for this organization.

It is off by default, and only an organization admin can turn it on:
  Atlassian Administration (admin.atlassian.com) -> select the organization
  -> Rovo -> Rovo MCP server -> Authentication -> API token: on

At a company this is an admin request, not something a developer can do, and
it is the first thing to ask for when proposing this pipeline (ADR-0003)."""


async def _check_jira_read(session, config: Config) -> str | None:
    """Run the smallest real Jira read. Return a diagnosis if it fails, else None."""
    print("\nCan the pipeline read Jira?")
    cloud = config.cloud_id or config.site_url
    if not (cloud and config.project_key):
        return (
            "Jira read NOT checked: needs JIRA_CLOUD_ID (or JIRA_SITE_URL) and\n"
            "AIDLC_PROJECT_KEY in .env. Every Jira tool requires a cloudId, and the\n"
            "check searches the configured project."
        )

    jql = f"project = {config.project_key}"
    result = await session.call_tool(
        "searchJiraIssuesUsingJql", {"cloudId": cloud, "jql": jql, "maxResults": 1}
    )
    error = _tool_error(result)
    if error:
        print(f"  searchJiraIssuesUsingJql ({jql}): REFUSED - {error}")
        if "connect via API token" in error:
            return API_TOKEN_DISABLED_DIAGNOSIS
        return "The Jira read was refused. See above."

    print(f"  searchJiraIssuesUsingJql ({jql}): OK")
    return None


async def _tools(config: Config) -> int:
    tools = await mcp_client.list_tools(config)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "tools.json"
    # by_alias so the dump carries the wire names (inputSchema, not input_schema).
    # This file is read as a reference for the server's actual contract.
    payload = [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"{len(tools)} tools written to {out.relative_to(REPO_ROOT)}\n")
    for tool in sorted(tools, key=lambda t: t.name):
        summary = (tool.description or "").strip().splitlines()
        print(f"  {tool.name:40} {summary[0][:70] if summary else ''}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aidlc",
        description="Local AI-DLC pipeline. Step 1: read a Jira card. See docs/PIPELINE.md",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Verify configuration and Jira connectivity")
    sub.add_parser("tools", help="Capture the MCP server's tool schemas for discovery")

    args = parser.parse_args(argv)

    try:
        config = config_mod.load()
    except ConfigError as err:
        print(str(err), file=sys.stderr)
        return 2

    handlers = {"doctor": _doctor, "tools": _tools}
    try:
        return asyncio.run(handlers[args.command](config))
    except KeyboardInterrupt:
        return 130
    except Exception as err:  # noqa: BLE001 - top level, must report not crash
        # Flatten task-group wrapping, or the user sees only
        # "unhandled errors in a TaskGroup (1 sub-exception)".
        print("", file=sys.stderr)
        for leaf in mcp_client.leaf_errors(err):
            print(f"{type(leaf).__name__}: {leaf}", file=sys.stderr)
        print(
            "\nIf this is a connection or protocol error, `uv run aidlc doctor` "
            "reports the HTTP status directly.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
