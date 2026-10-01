"""Configuration loading and validation.

No network. The MCP interaction is not covered here — it needs real credentials
and is verified by `aidlc doctor` instead.
"""

from __future__ import annotations

import base64

import pytest

from aidlc import config as config_mod
from aidlc.config import Config, ConfigError

JIRA_KEYS = (
    "JIRA_SITE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "CLAUDE_JIRA_TOKEN_API",
    "AIDLC_PROJECT_KEY",
    "AIDLC_TRIGGER_STATUS",
    "AIDLC_DONE_STATUS",
)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """Isolate from the developer's real .env and exported variables."""
    for key in JIRA_KEYS:
        monkeypatch.delenv(key, raising=False)
    empty = tmp_path / ".env"
    empty.write_text("", encoding="utf-8")
    return empty


def test_missing_config_reports_every_problem_at_once(clean_env):
    """One round trip per missing value is a bad setup experience."""
    with pytest.raises(ConfigError) as err:
        config_mod.load(clean_env)

    message = str(err.value)
    assert "JIRA_SITE_URL" in message
    assert "JIRA_EMAIL" in message
    assert "JIRA_API_TOKEN" in message


def test_old_token_name_is_named_explicitly(clean_env, monkeypatch):
    """The rename happened mid-build; the failure should explain itself."""
    monkeypatch.setenv("CLAUDE_JIRA_TOKEN_API", "leftover-value")

    with pytest.raises(ConfigError) as err:
        config_mod.load(clean_env)

    assert "CLAUDE_JIRA_TOKEN_API" in str(err.value)
    assert "JIRA_API_TOKEN" in str(err.value)


def test_email_is_required_because_the_token_alone_is_not_a_credential(clean_env, monkeypatch):
    monkeypatch.setenv("JIRA_SITE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("JIRA_API_TOKEN", "a-token")

    with pytest.raises(ConfigError) as err:
        config_mod.load(clean_env)

    assert "JIRA_EMAIL" in str(err.value)


def test_non_https_site_url_is_rejected(clean_env, monkeypatch):
    monkeypatch.setenv("JIRA_SITE_URL", "http://acme.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "dev@acme.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "a-token")

    with pytest.raises(ConfigError, match="https://"):
        config_mod.load(clean_env)


def test_trailing_slash_is_stripped_from_site_url(clean_env, monkeypatch):
    """A trailing slash is an easy paste error and breaks URL construction later."""
    monkeypatch.setenv("JIRA_SITE_URL", "https://acme.atlassian.net/")
    monkeypatch.setenv("JIRA_EMAIL", "dev@acme.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "a-token")

    assert config_mod.load(clean_env).site_url == "https://acme.atlassian.net"


def test_defaults_are_applied_for_optional_keys(clean_env, monkeypatch):
    monkeypatch.setenv("JIRA_SITE_URL", "https://acme.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "dev@acme.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "a-token")

    config = config_mod.load(clean_env)

    assert config.project_key is None
    assert config.trigger_status == "In development"
    assert config.done_status == "In review"


def _config(**overrides) -> Config:
    base = {
        "site_url": "https://acme.atlassian.net",
        "email": "dev@acme.com",
        "api_token": "secret-token-value",
        "project_key": "SCRUM",
        "trigger_status": "In development",
        "done_status": "In review",
    }
    return Config(**(base | overrides))


def test_auth_header_is_basic_base64_of_email_and_token():
    """ADR-0003: Authorization: Basic base64(email:api_token)."""
    header = _config().auth_header()

    scheme, encoded = header.split(" ", 1)
    assert scheme == "Basic"
    assert base64.b64decode(encoded).decode() == "dev@acme.com:secret-token-value"


def test_describe_never_leaks_the_token():
    """Guards the secret-safety invariant. doctor prints describe() output."""
    rendered = repr(_config().describe())

    assert "secret-token-value" not in rendered
    assert "18 chars" in rendered
