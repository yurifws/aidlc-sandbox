"""Stage 2: notice cards waiting in the trigger status.

ADR-0006 settles the mechanism (poll on current status), ADR-0009 the marker that
stops a card being picked up twice (a label).
"""

from __future__ import annotations

from typing import Any

from aidlc.config import Config
from aidlc.jira import mcp_client


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
