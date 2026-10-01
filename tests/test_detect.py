"""Stage 2 detection: the trigger query and how it is used. No network."""

from __future__ import annotations

import asyncio

import pytest

from aidlc import detect
from aidlc.detect import DetectError
from fakes import ScriptedSession, cfg, page


def test_trigger_query_matches_unlabelled_cards_too():
    """`labels NOT IN (...)` alone silently skips cards with no labels at all."""
    jql = detect.trigger_jql(cfg())

    assert jql == (
        'project = KAN AND status = "Development"'
        ' AND (labels IS EMPTY OR labels NOT IN ("aidlc-claimed"))'
        " ORDER BY created ASC"
    )


def test_trigger_query_uses_the_configured_status_and_label():
    jql = detect.trigger_jql(cfg(trigger_status="Ready for AI", claim_label="bot-taken"))

    assert 'status = "Ready for AI"' in jql
    assert 'NOT IN ("bot-taken")' in jql


def test_quotes_inside_a_status_name_cannot_break_the_query():
    jql = detect.trigger_jql(cfg(trigger_status='Dev "fast"'))

    assert 'status = "Dev \\"fast\\""' in jql


def test_detection_refuses_to_run_without_a_project():
    """Never search every project: the pipeline acts only on a board it was pointed at."""
    with pytest.raises(DetectError, match="AIDLC_PROJECT_KEY"):
        detect.trigger_jql(cfg(project_key=None))


def test_find_unclaimed_searches_with_the_trigger_query():
    session = ScriptedSession(page(["KAN-1", "KAN-4"]))

    keys = asyncio.run(detect.find_unclaimed(session, cfg()))

    assert keys == ["KAN-1", "KAN-4"]
    name, args = session.calls[0]
    assert name == "searchJiraIssuesUsingJql"
    assert args["jql"] == detect.trigger_jql(cfg())
