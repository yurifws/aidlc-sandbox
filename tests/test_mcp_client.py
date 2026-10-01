"""MCP adapter calls used by Step 2, against a scripted fake session. No network."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import pytest

from aidlc.config import Config
from aidlc.jira import mcp_client
from aidlc.jira.mcp_client import ToolCallError


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Result:
    content: list
    is_error: bool = False


def ok(payload) -> _Result:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return _Result(content=[_Block(body)])


def refused(message: str, status: int = 403) -> _Result:
    body = json.dumps({"error": True, "message": message, "statusCode": status})
    return _Result(content=[_Block(body)], is_error=True)


class ScriptedSession:
    """Returns the scripted results in order and records every call."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.results.pop(0)


def cfg(**overrides) -> Config:
    base = dict(
        email="dev@acme.com", api_token="t", site_url="https://acme.atlassian.net",
        cloud_id="11111111-1111-1111-1111-111111111111", project_key="KAN",
        trigger_status="Development", done_status="Review",
    )
    return Config(**(base | overrides))


def page(keys, *, last=True, token=None) -> _Result:
    data = {"isLast": last, "issues": [{"key": k} for k in keys]}
    if token:
        data["nextPageToken"] = token
    return ok({"data": data})


def run(coro):
    return asyncio.run(coro)


# --- search ------------------------------------------------------------------


def test_search_returns_keys_from_a_single_page():
    session = ScriptedSession(page(["KAN-1", "KAN-2"]))

    assert run(mcp_client.search_issue_keys(session, cfg(), "project = KAN")) == ["KAN-1", "KAN-2"]
    assert len(session.calls) == 1


def test_search_follows_pages_until_the_last():
    """Stopping at page one would silently drop cards once a board grows."""
    session = ScriptedSession(
        page(["KAN-1"], last=False, token="p2"),
        page(["KAN-2"], last=True),
    )

    keys = run(mcp_client.search_issue_keys(session, cfg(), "project = KAN", page_size=1))

    assert keys == ["KAN-1", "KAN-2"]
    assert "nextPageToken" not in session.calls[0][1]
    assert session.calls[1][1]["nextPageToken"] == "p2"


def test_search_refuses_to_page_forever():
    session = ScriptedSession(
        *[page([f"KAN-{i}"], last=False, token=f"p{i}") for i in range(mcp_client.MAX_SEARCH_PAGES)]
    )

    with pytest.raises(ToolCallError, match="still paging"):
        run(mcp_client.search_issue_keys(session, cfg(), "project = KAN"))


def test_search_refusal_raises_with_the_server_message():
    session = ScriptedSession(refused("Insufficient scopes. Required: [search:jira:agent-interface]"))

    with pytest.raises(ToolCallError, match="search:jira:agent-interface"):
        run(mcp_client.search_issue_keys(session, cfg(), "project = KAN"))


def test_every_call_needs_a_cloud_reference():
    session = ScriptedSession()

    with pytest.raises(ToolCallError, match="cloudId"):
        run(mcp_client.search_issue_keys(session, cfg(cloud_id=None, site_url=None), "x"))
    assert session.calls == []


def test_site_url_is_used_when_no_cloud_id_is_set():
    session = ScriptedSession(page([]))

    run(mcp_client.search_issue_keys(session, cfg(cloud_id=None), "project = KAN"))

    assert session.calls[0][1]["cloudId"] == "https://acme.atlassian.net"


# --- labels ------------------------------------------------------------------


def test_set_labels_sends_exactly_the_list_given():
    session = ScriptedSession(ok({"data": {"key": "KAN-1"}}))

    run(mcp_client.set_labels(session, cfg(), "KAN-1", ["frontend", "aidlc-claimed"]))

    name, args = session.calls[0]
    assert name == "editJiraIssue"
    assert args["issueIdOrKey"] == "KAN-1"
    assert args["fields"] == {"labels": ["frontend", "aidlc-claimed"]}


def test_set_labels_accepts_a_plain_text_success_body():
    """Only refusal matters; a non-JSON 'updated' must not read as failure."""
    session = ScriptedSession(ok("Issue KAN-1 updated"))

    run(mcp_client.set_labels(session, cfg(), "KAN-1", ["aidlc-claimed"]))


def test_set_labels_refusal_raises():
    session = ScriptedSession(refused("Insufficient scopes. Required: [write:jira:agent-interface]"))

    with pytest.raises(ToolCallError, match="editJiraIssue KAN-1"):
        run(mcp_client.set_labels(session, cfg(), "KAN-1", ["aidlc-claimed"]))


# --- json calls --------------------------------------------------------------


def test_call_json_rejects_a_non_object_payload():
    session = ScriptedSession(ok("[1, 2, 3]"))

    with pytest.raises(ToolCallError, match="expected a JSON object"):
        run(mcp_client.call_json(session, "anyTool", {}, "anyTool"))
