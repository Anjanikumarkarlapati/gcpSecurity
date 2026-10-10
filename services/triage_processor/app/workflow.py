from __future__ import annotations

from .models import WorkflowState as S

TRANSITIONS: dict[S, set[S]] = {
    S.NEW: {S.TRIAGING, S.ASSIGNED, S.MUTED, S.ACCEPTED_RISK},
    S.TRIAGING: {S.ASSIGNED, S.MUTED, S.ACCEPTED_RISK},
    S.ASSIGNED: {S.IN_REMEDIATION, S.TRIAGING, S.MUTED, S.ACCEPTED_RISK},
    S.IN_REMEDIATION: {S.PENDING_VERIFICATION, S.ASSIGNED, S.ACCEPTED_RISK},
    S.PENDING_VERIFICATION: {S.RESOLVED, S.IN_REMEDIATION},
    S.RESOLVED: {S.NEW},
    S.ACCEPTED_RISK: {S.NEW, S.TRIAGING},
    S.MUTED: {S.NEW, S.TRIAGING},
}
NEEDS_REASON = {S.MUTED, S.ACCEPTED_RISK}


class TransitionError(ValueError):
    pass


def check_transition(old: S, new: S, reason: str | None = None, expires_at: str | None = None) -> None:
    if new not in TRANSITIONS[old]:
        raise TransitionError(f"{old.value} -> {new.value} is not allowed")
    if new in NEEDS_REASON and not reason:
        raise TransitionError(f"{new.value} requires a reason")
    if new is S.ACCEPTED_RISK and not expires_at:
        raise TransitionError("ACCEPTED_RISK requires an expiry date")
