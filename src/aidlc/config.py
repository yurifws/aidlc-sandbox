"""Configuration loading and validation.

Every key is documented in `.env.example`. Validation collects all problems and
reports them together: configuring this involves three values from two different
Atlassian screens, and failing on them one at a time wastes a round trip each.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# ADR-0003. The /v2/ endpoint is deliberate: the /sse endpoint is deprecated and
# discontinued after 2026-06-30.
MCP_ENDPOINT = "https://mcp.atlassian.com/v2/mcp"

REPO_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Configuration is missing or malformed. Message is safe to print."""


@dataclass(frozen=True)
class Config:
    email: str
    api_token: str
    # Optional: the connection goes to MCP_ENDPOINT, not to the site. This is only
    # needed to build human-facing browse links like {site_url}/browse/ABC-123.
    site_url: str | None
    # Optional: most Atlassian MCP tools take a cloudId. Unconfirmed until `tools`
    # has run, and the server can report accessible cloud IDs itself, so this is a
    # convenience rather than a requirement.
    cloud_id: str | None
    project_key: str | None
    trigger_status: str
    done_status: str
    mcp_endpoint: str = MCP_ENDPOINT

    def auth_header(self) -> str:
        """Atlassian personal API token auth: Basic base64(email:token).

        The token alone is not a credential; the email is half of it. This is the
        single most common setup mistake, hence the explicit note.
        """
        raw = f"{self.email}:{self.api_token}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def mcp_headers(self) -> dict[str, str]:
        return {"Authorization": self.auth_header()}

    def describe(self) -> dict[str, str]:
        """Config summary safe to print. Never includes the token value."""
        return {
            "email": self.email,
            "api_token": f"set ({len(self.api_token)} chars)",
            "mcp_endpoint": self.mcp_endpoint,
            "site_url": self.site_url or "(unset, only needed for browse links)",
            "cloud_id": self.cloud_id or "(unset, doctor will report what is accessible)",
            "project_key": self.project_key or "(unset)",
        }


def load(env_file: Path | None = None) -> Config:
    load_dotenv(env_file or REPO_ROOT / ".env")

    problems: list[str] = []

    site_url = (os.getenv("JIRA_SITE_URL") or "").strip().rstrip("/")
    email = (os.getenv("JIRA_EMAIL") or "").strip()
    token = (os.getenv("JIRA_API_TOKEN") or "").strip()
    cloud_id = (os.getenv("JIRA_CLOUD_ID") or "").strip()

    # Only the credential is required. The MCP endpoint is fixed, so the site URL
    # plays no part in connecting, and blocking the gate command on a value it does
    # not use would be a pointless obstacle.
    if site_url and not site_url.startswith("https://"):
        problems.append(f"JIRA_SITE_URL must start with https:// (got {site_url!r})")
    if site_url and "atlassian.com" in site_url and "atlassian.net" not in site_url:
        problems.append(
            f"JIRA_SITE_URL looks like an Atlassian admin or Home URL ({site_url!r}).\n"
            "    Wanted: your Jira site, e.g. https://acme.atlassian.net\n"
            "    A home.atlassian.com or admin.atlassian.com link is not the site URL,\n"
            "    though its cloudId query parameter is a valid JIRA_CLOUD_ID"
        )

    if not email:
        problems.append("JIRA_EMAIL is not set; auth is base64(email:token), so the token alone is not enough")
    elif "@" not in email:
        problems.append(f"JIRA_EMAIL does not look like an email address (got {email!r})")

    if not token:
        problems.append(
            "JIRA_API_TOKEN is not set; create one at "
            "https://id.atlassian.com/manage-profile/security/api-tokens"
        )

    # Catch the pre-ADR-0003 name so the failure explains itself instead of
    # looking like a missing token.
    if not token and os.getenv("CLAUDE_JIRA_TOKEN_API"):
        problems.append(
            "found CLAUDE_JIRA_TOKEN_API; this was renamed to JIRA_API_TOKEN "
            "(the credential belongs to Jira, not to Claude). See .env.example"
        )

    if problems:
        raise ConfigError(
            "Configuration is incomplete:\n"
            + "\n".join(f"  - {p}" for p in problems)
            + "\n\nCopy .env.example to .env and fill it in. See docs/SETUP.md"
        )

    return Config(
        email=email,
        api_token=token,
        site_url=site_url or None,
        cloud_id=cloud_id or None,
        project_key=(os.getenv("AIDLC_PROJECT_KEY") or "").strip() or None,
        trigger_status=(os.getenv("AIDLC_TRIGGER_STATUS") or "In development").strip(),
        done_status=(os.getenv("AIDLC_DONE_STATUS") or "In review").strip(),
    )
