"""MCP client for the official Atlassian server.

The pipeline is itself the MCP client; no model sits in this path (ADR-0005).
Everything transport- and auth-specific is confined to this module, so switching
to the Jira REST API later would touch only this file.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from aidlc.config import Config


class ToolCallError(RuntimeError):
    """The server refused a tool call. The message is the server's, safe to print."""


def result_text(result: object) -> str:
    """The text content of a tool result, untruncated.

    Content blocks are typed (text, image, resource); only text carries data for
    this pipeline, so other blocks are named rather than dropped silently.
    """
    blocks = getattr(result, "content", None) or []
    parts: list[str] = []
    for block in blocks:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else f"<{getattr(block, 'type', 'unknown')} block>")
    return "\n".join(parts).strip()


def result_error(result: object) -> str | None:
    """Return an error description if a tool call failed, else None.

    A failed tool call does not raise. MCP can report failure two ways, and the
    Atlassian server uses the second: `isError` may be false while the content is
    a JSON body carrying `"error": true` and an HTTP status. Checking only
    `isError` makes a wall of 401s look like success, which is worse than an
    outright crash because it gets reported as working.
    """
    text = result_text(result)

    # Parse before consulting is_error: a JSON body gives a readable message,
    # where the raw text is a wall of escaped JSON.
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        payload = None

    if isinstance(payload, dict) and payload.get("error"):
        status = payload.get("statusCode")
        message = payload.get("message") or "unspecified error"
        return message + (f" (HTTP {status})" if status else "")

    if getattr(result, "is_error", False):
        return text[:400] or "(error with empty body)"
    return None


@contextlib.asynccontextmanager
async def connect(config: Config) -> AsyncIterator[ClientSession]:
    """Open an initialized MCP session.

    `streamable_http_client` takes no `headers` argument; a pre-configured httpx
    client is the documented way to supply them. Verified against the installed
    SDK rather than assumed, because ADR-0003 recorded this as unknown.

    We create the http client, so we own its lifecycle — the transport only
    manages a client it created itself.
    """
    async with create_mcp_http_client(headers=config.mcp_headers()) as http_client:
        async with streamable_http_client(
            config.mcp_endpoint, http_client=http_client
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


async def list_tools(config: Config) -> list[Any]:
    """Every tool the server exposes.

    Used for discovery: tool names are read off the live server, never guessed
    (ADR-0003).
    """
    async with connect(config) as session:
        return list((await session.list_tools()).tools)


async def call_tool(config: Config, name: str, arguments: dict[str, Any]) -> Any:
    async with connect(config) as session:
        return await session.call_tool(name, arguments)


async def fetch_issue(config: Config, key: str) -> dict[str, Any]:
    """Raw getJiraIssue payload for one issue. Raises ToolCallError if refused.

    view="evidence" because "compact" omits the issue type, labels and subtasks,
    which Stage 3 needs. Markdown is requested explicitly rather than relied on as
    the default; the server may still answer in HTML for content markdown cannot
    hold, and reports that in `appliedContentFormat`.
    """
    cloud = config.cloud_id or config.site_url
    if not cloud:
        raise ToolCallError(
            "every Jira tool needs a cloudId: set JIRA_CLOUD_ID or JIRA_SITE_URL in .env "
            "(`aidlc doctor` prints the cloud ID)"
        )
    async with connect(config) as session:
        result = await session.call_tool(
            "getJiraIssue",
            {
                "cloudId": cloud,
                "issueIdOrKey": key,
                "view": "evidence",
                "responseContentFormat": "markdown",
            },
        )
    if error := result_error(result):
        raise ToolCallError(f"getJiraIssue {key}: {error}")
    try:
        return json.loads(result_text(result))
    except ValueError as err:
        raise ToolCallError(f"getJiraIssue {key}: response was not JSON ({err})") from err


def leaf_errors(err: BaseException) -> Iterator[BaseException]:
    """Flatten nested ExceptionGroups to the exceptions that actually happened.

    anyio task groups wrap failures two levels deep, so the default repr of a
    connection failure is "unhandled errors in a TaskGroup (1 sub-exception)",
    which tells the user nothing.
    """
    subs = getattr(err, "exceptions", None)
    if subs:
        for sub in subs:
            yield from leaf_errors(sub)
    else:
        yield err


async def probe(config: Config) -> tuple[int, str]:
    """POST a bare `initialize` over plain HTTP and return (status, body).

    The protocol client reports every transport failure as JSON-RPC -32603 with
    no HTTP status attached, which makes a rejected credential look identical to
    a server fault. `doctor` needs the status code to give a useful diagnosis, so
    it asks the endpoint directly rather than inferring.
    """
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "aidlc", "version": "0.1.0"},
        },
    }
    headers = {
        **config.mcp_headers(),
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    async with httpx2.AsyncClient(timeout=30.0) as client:
        response = await client.post(config.mcp_endpoint, json=body, headers=headers)
        return response.status_code, response.text[:400]
