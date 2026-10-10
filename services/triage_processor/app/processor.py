"""Core triage logic: parse -> dedup -> enrich -> score -> persist -> notify -> audit."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from . import dedup
from .enrich import enrich
from .models import Case, Finding, WorkflowState as S
from .notifier import Notifier
from .scoring import due_date, score
from .store import Store, matching_mute_rule

SEVERITY_RANK = {"SEVERITY_UNSPECIFIED": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
CLOSED = {S.RESOLVED, S.MUTED, S.ACCEPTED_RISK}


@dataclass
class Result:
    action: str            # created | recurrence | updated | severity_increased | pending_verification | muted | duplicate_event | noop
    finding_uid: Optional[str] = None


class Processor:
    def __init__(self, store: Store, notifier: Notifier, sink=None):
        self.store, self.notifier, self.sink = store, notifier, sink

    # -- helpers -----------------------------------------------------
    def _audit(self, uid: str, action: str, old=None, new=None, reason=None, actor="system", now=None):
        ev = {"finding_uid": uid, "actor": actor, "action": action, "old_state": old,
              "new_state": new, "reason": reason, "timestamp": now or datetime.now(timezone.utc)}
        self.store.add_audit(ev)
        if self.sink:
            self.sink.write_event(ev)

    def _save(self, case: Case):
        self.store.save(case)
        if self.sink:
            self.sink.write_case(case)

    def _new_case(self, f: Finding, key: str, recurrence: int) -> Case:
        e = enrich(f)
        s = score(f.severity, e, recurrence_count=recurrence)
        now = f.event_time
        return Case(
            finding_uid=dedup.finding_uid(key, recurrence), dedup_key=key,
            finding_name=f.finding_name, source_id=f.source_id, finding_id=f.finding_id,
            project_id=f.project_id, resource_name=f.resource_name, category=f.category,
            severity=f.severity, scc_state=f.scc_state,
            workflow_state=S.NEW if e.routed_to_review_queue else S.ASSIGNED,
            calculated_priority=s.priority, risk_score=s.total, risk_reasons=s.reasons,
            owner_team=e.owner_team, environment=e.environment,
            recommended_action=e.recommended_action,
            first_seen_at=now, last_seen_at=now, due_date=due_date(s.priority, now),
            recurrence_count=recurrence, enrichment=e,
        )

    # -- entry point -------------------------------------------------
    def process(self, f: Finding) -> Result:
        eid = dedup.event_id(f)
        if self.store.seen_event(eid):
            return Result("duplicate_event")

        key = dedup.dedup_key(f)
        existing = self.store.get_by_dedup(key)
        result = self._handle(f, key, existing)
        self.store.mark_event(eid)  # only after success so retries re-run
        return result

    def _handle(self, f: Finding, key: str, existing: Optional[Case]) -> Result:
        if existing is None:
            return self._create(f, key, recurrence=0)

        # Recurrence: active again after the earlier case was closed by resolution.
        if existing.workflow_state is S.RESOLVED and f.scc_state == "ACTIVE":
            return self._create(f, key, recurrence=existing.recurrence_count + 1, previous=existing)

        if f.scc_state == "INACTIVE":
            if existing.workflow_state in CLOSED | {S.PENDING_VERIFICATION}:
                return Result("noop", existing.finding_uid)
            old = existing.workflow_state
            existing.workflow_state = S.PENDING_VERIFICATION
            existing.scc_state = "INACTIVE"
            existing.last_seen_at = f.event_time
            self._save(existing)
            self._audit(existing.finding_uid, "scc_inactive", old.value, S.PENDING_VERIFICATION.value,
                        "SCC reports finding inactive", now=f.event_time)
            return Result("pending_verification", existing.finding_uid)

        if SEVERITY_RANK.get(f.severity, 0) > SEVERITY_RANK.get(existing.severity, 0):
            old_sev, old_pri = existing.severity, existing.calculated_priority
            e = existing.enrichment or enrich(f)
            age = (f.event_time - existing.first_seen_at).days
            s = score(f.severity, e, age_days=age, recurrence_count=existing.recurrence_count)
            existing.severity, existing.risk_score = f.severity, s.total
            existing.calculated_priority, existing.risk_reasons = s.priority, s.reasons
            existing.due_date = min(existing.due_date, due_date(s.priority, f.event_time))
            existing.last_seen_at = f.event_time
            self._save(existing)
            self._audit(existing.finding_uid, "severity_increased", old_sev, f.severity,
                        f"priority {old_pri} -> {s.priority}", now=f.event_time)
            if s.priority == "P1" and existing.workflow_state not in CLOSED:
                self.notifier.notify(existing, "severity increased")
            return Result("severity_increased", existing.finding_uid)

        existing.last_seen_at = f.event_time  # unchanged repeat: refresh timestamp only
        self._save(existing)
        return Result("updated", existing.finding_uid)

    def _create(self, f: Finding, key: str, recurrence: int, previous: Optional[Case] = None) -> Result:
        case = self._new_case(f, key, recurrence)
        rule = matching_mute_rule(self.store.mute_rules(), f.category, f.resource_name, f.event_time)
        if rule:
            case.workflow_state = S.MUTED
            self._save(case)
            self._audit(case.finding_uid, "auto_muted", None, S.MUTED.value, rule.get("reason"), now=f.event_time)
            return Result("muted", case.finding_uid)

        self._save(case)
        reason = "recurrence of a resolved finding" if previous else "new finding"
        self._audit(case.finding_uid, "recurrence" if previous else "created", None,
                    case.workflow_state.value, reason, now=f.event_time)
        if previous:
            self._audit(previous.finding_uid, "recurred_as", None, case.finding_uid, now=f.event_time)
        if case.calculated_priority == "P1":
            self.notifier.notify(case, reason)
        return Result("recurrence" if previous else "created", case.finding_uid)
