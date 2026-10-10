from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class WorkflowState(str, Enum):
    NEW = "NEW"
    TRIAGING = "TRIAGING"
    ASSIGNED = "ASSIGNED"
    IN_REMEDIATION = "IN_REMEDIATION"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    RESOLVED = "RESOLVED"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    MUTED = "MUTED"


@dataclass
class Finding:
    """Normalised SCC finding."""
    finding_name: str          # organizations/1/sources/2/findings/3
    source_id: str
    finding_id: str
    category: str
    severity: str
    scc_state: str             # ACTIVE | INACTIVE
    resource_name: str
    project_id: str
    event_time: datetime
    resource_type: str = ""
    labels: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


@dataclass
class Enrichment:
    owner_team: str
    environment: str
    is_publicly_exposed: bool
    data_sensitivity: str      # sensitive | normal
    high_criticality: bool
    recommended_action: str
    routed_to_review_queue: bool = False


@dataclass
class Score:
    total: int
    priority: str
    reasons: list[str]


@dataclass
class Case:
    finding_uid: str
    dedup_key: str
    finding_name: str
    source_id: str
    finding_id: str
    project_id: str
    resource_name: str
    category: str
    severity: str
    scc_state: str
    workflow_state: WorkflowState
    calculated_priority: str
    risk_score: int
    risk_reasons: list[str]
    owner_team: str
    environment: str
    recommended_action: str
    first_seen_at: datetime
    last_seen_at: datetime
    due_date: datetime
    assignee: Optional[str] = None
    recurrence_count: int = 0
    triage_notes: list[dict] = field(default_factory=list)
    resolved_at: Optional[datetime] = None
    # Enrichment inputs kept so rescoring doesn't need to re-enrich.
    enrichment: Optional[Enrichment] = None
