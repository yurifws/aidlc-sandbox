"""Diagnosis helpers in the CLI.

The messages below are copied from real responses of the Atlassian MCP server, so
these tests pin the parsing to what the server actually says.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from aidlc.cli import REQUIRED_SCOPES, _missing_scopes_diagnosis, _tool_error

CLASSIC_TOKEN_MESSAGE = (
    'Unable to resolve user scopes from the user-context token for "atlassianUserInfo". '
    "The session token is missing the scope claim required to authorize this operation."
)
MISSING_SCOPES_MESSAGE = (
    'Insufficient scopes for "getAccessibleAtlassianResources". '
    "Required: [read:me, read:account]. Use discover to find endpoints you have access to."
)


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Result:
    content: list
    is_error: bool = False


def _error_result(message: str, status: int) -> _Result:
    body = json.dumps({"error": True, "message": message, "statusCode": status})
    return _Result(content=[_Block(body)], is_error=True)


def test_tool_error_extracts_message_and_status_from_json_body():
    error = _tool_error(_error_result(MISSING_SCOPES_MESSAGE, 403))

    assert error is not None
    assert error.startswith("Insufficient scopes")
    assert error.endswith("(HTTP 403)")


def test_successful_result_is_not_an_error():
    assert _tool_error(_Result(content=[_Block('{"accountId": "abc"}')])) is None


def test_required_scopes_are_parsed_from_the_server_message():
    match = REQUIRED_SCOPES.search(MISSING_SCOPES_MESSAGE)

    assert match is not None
    assert [s.strip() for s in match.group(1).split(",")] == ["read:me", "read:account"]


def test_classic_token_message_names_no_required_scopes():
    """The two scope failures need different fixes, so they must not be confused."""
    assert REQUIRED_SCOPES.search(CLASSIC_TOKEN_MESSAGE) is None
    assert "missing the scope claim" in CLASSIC_TOKEN_MESSAGE


def test_missing_scopes_diagnosis_lists_each_scope_and_does_not_blame_a_classic_token():
    text = _missing_scopes_diagnosis({"read:me", "read:account"})

    assert "read:me" in text
    assert "read:account" in text
    assert "CLASSIC" not in text
