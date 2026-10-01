"""Stage 2 detection: the trigger query and how it is used. No network."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from aidlc import detect
from aidlc.detect import DetectError
from fakes import ScriptedSession, cfg, ok, page, refused


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


# --- picking cards up --------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "getJiraIssue.KAN-1.evidence.json"


def issue_payload(key="KAN-1", labels=None):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["data"]["key"] = key
    payload["data"]["fields"]["labels"] = labels or []
    return ok(payload)


def tool_names(session):
    return [name for name, _ in session.calls]


def test_with_label_keeps_existing_labels_and_adds_ours_once():
    assert detect.with_label([], "aidlc-claimed") == ["aidlc-claimed"]
    assert detect.with_label(["frontend"], "aidlc-claimed") == ["frontend", "aidlc-claimed"]
    assert detect.with_label(["aidlc-claimed"], "aidlc-claimed") == ["aidlc-claimed"]


def test_pick_up_fetches_saves_then_claims(tmp_path):
    session = ScriptedSession(issue_payload(), ok({"data": {}}))

    result = asyncio.run(detect.pick_up(session, cfg(), "KAN-1", tmp_path))

    assert result.ok
    assert tool_names(session) == ["getJiraIssue", "editJiraIssue"]
    saved = json.loads((tmp_path / "KAN-1" / "issue.json").read_text(encoding="utf-8"))
    assert saved["key"] == "KAN-1" and saved["status"] == "Development"
    assert not (tmp_path / "KAN-1" / "issue.json.tmp").exists()


def test_claiming_keeps_the_labels_a_person_put_on_the_card(tmp_path):
    """editJiraIssue replaces the list; sending only ours would delete theirs."""
    session = ScriptedSession(issue_payload(labels=["frontend", "urgent"]), ok({"data": {}}))

    asyncio.run(detect.pick_up(session, cfg(), "KAN-1", tmp_path))

    _, edit_args = session.calls[1]
    assert edit_args["fields"]["labels"] == ["frontend", "urgent", "aidlc-claimed"]


def test_a_card_that_cannot_be_fetched_is_not_claimed(tmp_path):
    """Left unclaimed, the next poll retries it."""
    session = ScriptedSession(refused('Issue "KAN-1" not found', 404))

    result = asyncio.run(detect.pick_up(session, cfg(), "KAN-1", tmp_path))

    assert not result.ok and "not found" in result.detail
    assert tool_names(session) == ["getJiraIssue"]
    assert not (tmp_path / "KAN-1").exists()


def test_a_card_that_cannot_be_saved_is_not_claimed(tmp_path):
    blocker = tmp_path / "runs"
    blocker.write_text("a file where the runs directory should be", encoding="utf-8")
    session = ScriptedSession(issue_payload())

    result = asyncio.run(detect.pick_up(session, cfg(), "KAN-1", blocker))

    assert not result.ok
    assert tool_names(session) == ["getJiraIssue"]


def test_a_failed_claim_is_reported_and_the_handoff_file_kept(tmp_path):
    """The next poll re-fetches and overwrites the same file, which is harmless."""
    session = ScriptedSession(issue_payload(), refused("Required: [write:jira:agent-interface]"))

    result = asyncio.run(detect.pick_up(session, cfg(), "KAN-1", tmp_path))

    assert not result.ok and "editJiraIssue KAN-1" in result.detail
    assert (tmp_path / "KAN-1" / "issue.json").exists()


def test_one_failing_card_does_not_stop_the_others(tmp_path):
    session = ScriptedSession(
        page(["KAN-1", "KAN-2"]),
        refused('Issue "KAN-1" not found', 404),
        issue_payload("KAN-2"), ok({"data": {}}),
    )

    results = asyncio.run(detect.run_cycle(session, cfg(), tmp_path))

    assert [(r.key, r.ok) for r in results] == [("KAN-1", False), ("KAN-2", True)]
    assert (tmp_path / "KAN-2" / "issue.json").exists()


def test_an_empty_poll_picks_nothing_up(tmp_path):
    session = ScriptedSession(page([]))

    assert asyncio.run(detect.run_cycle(session, cfg(), tmp_path)) == []
    assert tool_names(session) == ["searchJiraIssuesUsingJql"]
