from __future__ import annotations

import logging
import os
from typing import Protocol

import httpx

from .models import Case

log = logging.getLogger("notifier")
SCC_LINK = "https://console.cloud.google.com/security/command-center/findings"


def format_message(case: Case, reason: str) -> str:
    return (
        f"[{case.calculated_priority}] {case.category} ({case.severity}) - {reason}\n"
        f"Project: {case.project_id} | Resource: {case.resource_name}\n"
        f"Owner: {case.owner_team} | Score: {case.risk_score} | Due: {case.due_date:%Y-%m-%d}\n"
        f"Why: {'; '.join(case.risk_reasons)}\n"
        f"Action: {case.recommended_action}\n"
        f"SCC: {SCC_LINK}"
    )


class Notifier(Protocol):
    def notify(self, case: Case, reason: str) -> None: ...


class LogNotifier:
    def notify(self, case, reason):
        log.warning(format_message(case, reason))


class RecordingNotifier:
    """For tests."""
    def __init__(self): self.sent: list[tuple[str, str]] = []
    def notify(self, case, reason): self.sent.append((case.finding_uid, reason))


class SlackNotifier:
    def __init__(self, webhook_url: str):
        self.url = webhook_url

    def notify(self, case, reason):
        try:
            httpx.post(self.url, json={"text": format_message(case, reason)}, timeout=5).raise_for_status()
        except httpx.HTTPError:
            # Never fail ingestion because Slack is down; the case is already persisted.
            log.exception("slack notification failed for %s", case.finding_uid)


def from_env() -> Notifier:
    # The webhook comes from Secret Manager, mounted as an env var by Cloud Run.
    url = os.environ.get("SLACK_WEBHOOK_URL")
    return SlackNotifier(url) if url else LogNotifier()
