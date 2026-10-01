"""The normalized issue: the contract between Stage 1 and every later stage.

Later stages read this shape, never the raw MCP payload, so a change in the
server's response format is absorbed here rather than rippling through the
pipeline. Field choices are recorded in docs/PIPELINE.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class IssueFormatError(ValueError):
    """The getJiraIssue payload did not have the expected shape."""


@dataclass(frozen=True)
class Issue:
    key: str
    # Built from JIRA_SITE_URL; the server's response carries no browse URL.
    url: str | None
    summary: str
    status: str
    issue_type: str | None
    priority: str | None
    labels: list[str]
    # Acceptance criteria live in here: this Jira instance has no separate field
    # for them, and extracting a section by heading would be guesswork that
    # silently drops criteria written any other way. Stage 3 reads the whole text.
    description: str
    # What the server actually sent: "markdown" normally, "html" when the body
    # holds content markdown cannot represent. Later stages must not assume.
    description_format: str
    # Keys of existing subtasks, so Stage 3 can tell a fresh card from one it
    # has already broken down.
    subtasks: list[str]
    updated: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _name(value: Any) -> str | None:
    return value.get("name") if isinstance(value, dict) else None


def from_mcp(payload: dict[str, Any], site_url: str | None) -> Issue:
    """Normalize a getJiraIssue (view="evidence") payload."""
    data = payload.get("data", payload) if isinstance(payload, dict) else None
    try:
        key = data["key"]
        fields = data["fields"]
        summary = fields["summary"]
        status = fields["status"]["name"]
    except (KeyError, TypeError) as err:
        raise IssueFormatError(f"unexpected getJiraIssue response, missing {err}") from err

    return Issue(
        key=key,
        url=f"{site_url}/browse/{key}" if site_url else None,
        summary=summary,
        status=status,
        issue_type=_name(fields.get("issuetype")),
        priority=_name(fields.get("priority")),
        labels=list(fields.get("labels") or []),
        description=fields.get("description") or "",
        description_format=data.get("appliedContentFormat") or "unknown",
        subtasks=[s["key"] for s in fields.get("subtasks") or [] if isinstance(s, dict) and "key" in s],
        updated=fields.get("updated"),
    )
