"""Workflow persistence. InMemoryStore for tests/local; FirestoreStore for GCP."""
from __future__ import annotations

import fnmatch
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterable, Optional, Protocol

from .models import Case, Enrichment, WorkflowState


def case_to_dict(c: Case) -> dict:
    d = asdict(c)
    d["workflow_state"] = c.workflow_state.value
    return d


def case_from_dict(d: dict) -> Case:
    d = dict(d)
    d["workflow_state"] = WorkflowState(d["workflow_state"])
    if d.get("enrichment"):
        d["enrichment"] = Enrichment(**d["enrichment"])
    return Case(**d)


class Store(Protocol):
    def seen_event(self, event_id: str) -> bool: ...
    def mark_event(self, event_id: str) -> None: ...
    def get_by_dedup(self, key: str) -> Optional[Case]: ...
    def get(self, uid: str) -> Optional[Case]: ...
    def save(self, case: Case) -> None: ...
    def list(self, **filters) -> list[Case]: ...
    def add_audit(self, event: dict) -> None: ...
    def audit_for(self, uid: str) -> list[dict]: ...
    def mute_rules(self) -> list[dict]: ...


def matching_mute_rule(rules: Iterable[dict], category: str, resource_name: str,
                       now: datetime | None = None) -> Optional[dict]:
    now = now or datetime.now(timezone.utc)
    for r in rules:
        exp = r.get("expires_at")
        if exp and exp < now:
            continue
        if r.get("category") not in (None, category):
            continue
        if fnmatch.fnmatch(resource_name, r.get("resource_pattern", "*")):
            return r
    return None


def _match(c: Case, filters: dict) -> bool:
    return all(v is None or getattr(c, k, None) == v or getattr(getattr(c, k, None), "value", None) == v
               for k, v in filters.items())


class InMemoryStore:
    def __init__(self, mute_rules: list[dict] | None = None):
        self._cases: dict[str, Case] = {}
        self._by_key: dict[str, str] = {}
        self._events: set[str] = set()
        self._audit: list[dict] = []
        self._mutes = mute_rules or []

    def seen_event(self, event_id): return event_id in self._events
    def mark_event(self, event_id): self._events.add(event_id)

    def get_by_dedup(self, key):
        uid = self._by_key.get(key)
        return self._cases.get(uid) if uid else None

    def get(self, uid): return self._cases.get(uid)

    def save(self, case):
        self._cases[case.finding_uid] = case
        self._by_key[case.dedup_key] = case.finding_uid

    def list(self, **filters):
        return [c for c in self._cases.values() if _match(c, filters)]

    def add_audit(self, event): self._audit.append(event)
    def audit_for(self, uid): return [e for e in self._audit if e["finding_uid"] == uid]
    def mute_rules(self): return self._mutes


class FirestoreStore:
    def __init__(self, project: str | None = None):
        from google.cloud import firestore  # lazy: not needed for tests
        self.db = firestore.Client(project=project)

    def seen_event(self, event_id):
        return self.db.collection("processed_events").document(event_id).get().exists

    def mark_event(self, event_id):
        self.db.collection("processed_events").document(event_id).set(
            {"at": datetime.now(timezone.utc)})

    def get_by_dedup(self, key):
        docs = (self.db.collection("findings").where("dedup_key", "==", key)
                .order_by("first_seen_at", direction="DESCENDING").limit(1).stream())
        return next((case_from_dict(d.to_dict()) for d in docs), None)

    def get(self, uid):
        d = self.db.collection("findings").document(uid).get()
        return case_from_dict(d.to_dict()) if d.exists else None

    def save(self, case):
        self.db.collection("findings").document(case.finding_uid).set(case_to_dict(case))

    def list(self, **filters):
        q = self.db.collection("findings")
        for k, v in filters.items():
            if v is not None:
                q = q.where(k, "==", v)
        return [case_from_dict(d.to_dict()) for d in q.limit(500).stream()]

    def add_audit(self, event):
        self.db.collection("audit_events").add(event)

    def audit_for(self, uid):
        return [d.to_dict() for d in
                self.db.collection("audit_events").where("finding_uid", "==", uid).stream()]

    def mute_rules(self):
        return [d.to_dict() for d in self.db.collection("mute_rules").stream()]
