"""Normalization of a real getJiraIssue response.

The fixture is a response from the live server for KAN-1, with the reporter's
account details replaced by placeholders because this repository is public.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidlc.jira.models import IssueFormatError, from_mcp

FIXTURE = Path(__file__).parent / "fixtures" / "getJiraIssue.KAN-1.evidence.json"


@pytest.fixture
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_core_fields_are_normalized(payload):
    issue = from_mcp(payload, "https://acme.atlassian.net")

    assert issue.key == "KAN-1"
    assert issue.summary == "Add a --version flag to the aidlc CLI"
    assert issue.status == "Development"
    assert issue.issue_type == "Task"
    assert issue.priority == "Medium"
    assert issue.labels == []
    assert issue.subtasks == []


def test_browse_url_is_built_from_the_site_url(payload):
    """The response carries no URL, so it has to be constructed."""
    assert from_mcp(payload, "https://acme.atlassian.net").url == (
        "https://acme.atlassian.net/browse/KAN-1"
    )
    assert from_mcp(payload, None).url is None


def test_description_arrives_as_markdown_with_criteria_intact(payload):
    issue = from_mcp(payload, None)

    assert issue.description_format == "markdown"
    assert "**Acceptance criteria**" in issue.description
    assert "* A test covers the flag" in issue.description
    assert "`uv run aidlc --version`" in issue.description


def test_normalized_output_carries_no_personal_data(payload):
    """Reporter and assignee are deliberately not part of the contract."""
    rendered = json.dumps(from_mcp(payload, None).to_dict())

    assert "accountId" not in rendered
    assert "displayName" not in rendered


def test_missing_description_becomes_empty_text(payload):
    payload["data"]["fields"]["description"] = None

    assert from_mcp(payload, None).description == ""


def test_unexpected_shape_is_a_clear_error_not_a_key_error():
    with pytest.raises(IssueFormatError, match="missing"):
        from_mcp({"data": {"key": "KAN-1"}}, None)
