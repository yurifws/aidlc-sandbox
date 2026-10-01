"""Command line entry point.

argparse rather than click/typer: three subcommands do not justify a dependency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
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
        reported = False
        for tool in identity:
            if (tool.inputSchema or {}).get("required"):
                print(f"  {tool.name}: skipped, needs arguments")
                continue
            try:
                result = await session.call_tool(tool.name, {})
            except Exception as err:  # noqa: BLE001 - diagnostic, keep going
                print(f"  {tool.name}: failed ({type(err).__name__})")
                continue
            reported = True
            print(f"  {tool.name}:")
            for line in _render(result).splitlines():
                print(f"    {line}")
        if not identity:
            print("  (no identity tools matched; see `aidlc tools` for the full list)")
        elif not reported:
            print("  (none callable without arguments; see `aidlc tools`)")

        print("\nCandidate issue tools:")
        print("\n".join(f"  {n}" for n in issue) or "  (none matched)")

    print("\nOK. Auth works. Next: `uv run aidlc tools` to capture the full schemas.")
    return 0


async def _tools(config: Config) -> int:
    tools = await mcp_client.list_tools(config)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "tools.json"
    payload = [t.model_dump(mode="json", exclude_none=True) for t in tools]
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
