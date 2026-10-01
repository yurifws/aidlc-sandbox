"""Fakes shared by the tests: scripted MCP sessions and a ready-made config.

A scripted session stands in for the server so tests run without network. The
payload shapes mirror real responses captured from the Atlassian MCP server.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from aidlc.config import Config


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
