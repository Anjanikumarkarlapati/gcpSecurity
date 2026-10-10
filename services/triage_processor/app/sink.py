"""Optional BigQuery sink for triage_cases / triage_events."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from .models import Case

log = logging.getLogger("sink")


class BigQuerySink:
    def __init__(self, dataset: str):  # "project.dataset"
        from google.cloud import bigquery
        self.client = bigquery.Client()
        self.dataset = dataset

    def _insert(self, table: str, row: dict):
        errors = self.client.insert_rows_json(f"{self.dataset}.{table}", [row])
        if errors:
            # Analytics are best-effort; workflow state in Firestore is the source of truth.
            log.error("BigQuery insert into %s failed: %s", table, errors)

    def write_case(self, c: Case):
        now = datetime.now(timezone.utc).isoformat()
        self._insert("triage_cases", {
            "finding_uid": c.finding_uid, "dedup_key": c.dedup_key, "category": c.category,
            "severity": c.severity, "current_priority": c.calculated_priority,
            "risk_score": c.risk_score, "owner_team": c.owner_team, "assignee": c.assignee,
            "state": c.workflow_state.value, "project_id": c.project_id,
            "resource_name": c.resource_name, "first_seen_at": c.first_seen_at.isoformat(),
            "last_seen_at": c.last_seen_at.isoformat(), "due_date": c.due_date.isoformat(),
            "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
            "recurrence_count": c.recurrence_count,
            "sla_breached": c.due_date < datetime.now(timezone.utc)
            and c.workflow_state.value not in ("RESOLVED", "MUTED", "ACCEPTED_RISK"),
            "snapshot_time": now,
        })

    def write_event(self, ev: dict):
        self._insert("triage_events", {
            "event_id": str(uuid.uuid4()), "finding_uid": ev["finding_uid"],
            "event_type": ev["action"], "actor": ev["actor"],
            "timestamp": ev["timestamp"].isoformat(),
            "metadata": json.dumps({k: ev.get(k) for k in ("old_state", "new_state", "reason")}),
        })
