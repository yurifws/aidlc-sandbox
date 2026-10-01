"""Stage 2: notice cards waiting in the trigger status.

ADR-0006 settles the mechanism (poll on current status), ADR-0009 the marker that
stops a card being picked up twice (a label).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aidlc.config import Config
from aidlc.jira import mcp_client, models
from aidlc.jira.models import Issue


class DetectError(RuntimeError):
    """Detection cannot run with this configuration. Message is safe to print."""


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def trigger_jql(config: Config) -> str:
    """The query for cards waiting to be picked up.

    `labels IS EMPTY OR` is not decoration. On its own, `labels NOT IN (...)` does
    not match a card that has no labels at all -- verified on the live board -- so
    without it a fresh card would never be found, and nothing would error.
    Oldest first, so cards are handled in the order they arrived.
    """
    if not config.project_key:
        raise DetectError(
            "AIDLC_PROJECT_KEY is not set. The pipeline only ever searches one project, "
            "so that it cannot act on a board nobody pointed it at."
        )
    return (
        f"project = {config.project_key}"
        f" AND status = {_quote(config.trigger_status)}"
        f" AND (labels IS EMPTY OR labels NOT IN ({_quote(config.claim_label)}))"
        " ORDER BY created ASC"
    )


async def find_unclaimed(session: Any, config: Config) -> list[str]:
    """Keys of cards in the trigger status that the pipeline has not claimed."""
    return await mcp_client.search_issue_keys(session, config, trigger_jql(config))


def with_label(labels: list[str], label: str) -> list[str]:
    """The card's labels plus ours, keeping every existing one.

    editJiraIssue replaces the whole list, so dropping an existing label here
    would delete it from the card (ADR-0009).
    """
    return list(labels) if label in labels else [*labels, label]


def save_issue(issue: Issue, runs_dir: Path) -> Path:
    """Write the handoff file Stage 3 starts from: <runs_dir>/<KEY>/issue.json.

    Written to a temporary name and renamed into place, so a reader never sees a
    half-written file.
    """
    run_dir = runs_dir / issue.key
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "issue.json"
    tmp = path.with_name("issue.json.tmp")
    tmp.write_text(json.dumps(issue.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


@dataclass(frozen=True)
class Pickup:
    key: str
    ok: bool
    # The handoff file written, or why the card was left for the next poll.
    detail: str


async def pick_up(session: Any, config: Config, key: str, runs_dir: Path) -> Pickup:
    """Fetch, save, then claim one card.

    The order is the point (ADR-0009): the claim comes last, so any failure before
    it leaves the card unclaimed and the next poll retries it, instead of leaving
    it marked as taken with nothing done.
    """
    try:
        issue = models.from_mcp(await mcp_client.get_issue(session, config, key), config.site_url)
        path = save_issue(issue, runs_dir)
        await mcp_client.set_labels(session, config, key, with_label(issue.labels, config.claim_label))
    except (mcp_client.ToolCallError, models.IssueFormatError, OSError) as err:
        return Pickup(key, ok=False, detail=str(err))
    return Pickup(key, ok=True, detail=str(path))


async def run_cycle(session: Any, config: Config, runs_dir: Path) -> list[Pickup]:
    """One poll: find every waiting card and pick each one up.

    One card failing does not stop the others; each result says what happened.
    """
    return [await pick_up(session, config, key, runs_dir) for key in await find_unclaimed(session, config)]
