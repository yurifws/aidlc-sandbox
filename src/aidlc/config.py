"""Configuration loading and validation.

Every key is documented in `.env.example`. Validation collects all problems and
reports them together: configuring this involves three values from two different
Atlassian screens, and failing on them one at a time wastes a round trip each.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# ADR-0003. The /v2/ endpoint is deliberate: the /sse endpoint is deprecated and
# discontinued after 2026-06-30.
MCP_ENDPOINT = "https://mcp.atlassian.com/v2/mcp"

REPO_ROOT = Path(__file__).resolve().parents[2]

PROJECT_KEY = re.compile(r"[A-Z][A-Z0-9_]+")
LABEL = re.compile(r"[^\s,]+")
# Each poll is a search against Jira; faster than this is load without benefit
# for cards that wait minutes to hours in a column.
MIN_POLL_INTERVAL = 10
# A breakdown is one planning task; a cap above this is more likely a typo
# (20 for 2.0) than an intention.
MAX_BREAKDOWN_BUDGET_USD = 20.0


class ConfigError(RuntimeError):
    """Configuration is missing or malformed. Message is safe to print."""


@dataclass(frozen=True)
class Config:
    email: str
    api_token: str
    # The connection goes to MCP_ENDPOINT, not to the site. Every Jira tool needs
    # the site identified, by cloud_id or by this URL (both verified), and fetch
    # builds browse links from it. Optional only so that `doctor` can run first
    # and report the cloud ID.
    site_url: str | None
    cloud_id: str | None
    project_key: str | None
    trigger_status: str
    done_status: str
    # ADR-0009: marks a card the pipeline has picked up.
    claim_label: str = "aidlc-claimed"
    # ADR-0006: seconds between polls in `aidlc watch`.
    poll_interval: int = 60
    # ADR-0010: model and spending cap for each Stage 3 breakdown run.
    breakdown_model: str = "claude-sonnet-5-5"
    breakdown_budget_usd: float = 2.0
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

    # The project key goes into JQL. Checking its shape keeps a typo from becoming
    # a query against something else, and keeps quoting out of the question.
    project_key = (os.getenv("AIDLC_PROJECT_KEY") or "").strip()
    if project_key and not PROJECT_KEY.fullmatch(project_key):
        problems.append(
            f"AIDLC_PROJECT_KEY must look like a Jira project key, e.g. KAN (got {project_key!r})"
        )

    claim_label = (os.getenv("AIDLC_CLAIM_LABEL") or "aidlc-claimed").strip()
    if not LABEL.fullmatch(claim_label):
        problems.append(
            f"AIDLC_CLAIM_LABEL must be one word without spaces or commas, as Jira "
            f"labels are (got {claim_label!r})"
        )

    raw_interval = (os.getenv("AIDLC_POLL_INTERVAL") or "60").strip()
    try:
        poll_interval = int(raw_interval)
    except ValueError:
        poll_interval = 0
    if poll_interval < MIN_POLL_INTERVAL:
        problems.append(
            f"AIDLC_POLL_INTERVAL must be a whole number of seconds, at least "
            f"{MIN_POLL_INTERVAL} (got {raw_interval!r})"
        )

    breakdown_model = (os.getenv("AIDLC_BREAKDOWN_MODEL") or "claude-sonnet-5-5").strip()

    raw_budget = (os.getenv("AIDLC_BREAKDOWN_BUDGET_USD") or "2.00").strip()
    try:
        breakdown_budget = float(raw_budget)
    except ValueError:
        breakdown_budget = 0.0
    if not 0 < breakdown_budget <= MAX_BREAKDOWN_BUDGET_USD:
        problems.append(
            f"AIDLC_BREAKDOWN_BUDGET_USD must be a dollar amount above 0 and at most "
            f"{MAX_BREAKDOWN_BUDGET_USD:.2f} (got {raw_budget!r})"
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
        project_key=project_key or None,
        trigger_status=(os.getenv("AIDLC_TRIGGER_STATUS") or "In development").strip(),
        done_status=(os.getenv("AIDLC_DONE_STATUS") or "In review").strip(),
        claim_label=claim_label,
        poll_interval=poll_interval,
        breakdown_model=breakdown_model,
        breakdown_budget_usd=breakdown_budget,
    )
