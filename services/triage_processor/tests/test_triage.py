from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.dedup import dedup_key
from app.enrich import enrich
from app.main import build_app
from app.models import WorkflowState as S
from app.parser import ParseError, decode_pubsub_message, parse_notification
from app.scoring import add_business_days, due_date, score
from app.store import InMemoryStore
from app.workflow import TransitionError, check_transition
from conftest import envelope, make_payload


# ---- parser ----
def test_parse_extracts_fields_and_trims_nanoseconds():
    f = parse_notification(make_payload())
    assert (f.source_id, f.finding_id, f.project_id) == ("2", "f1", "t051-production")
    assert f.event_time == datetime(2026, 10, 5, 10, 0, 0, 123456, tzinfo=timezone.utc)


@pytest.mark.parametrize("bad", [{}, {"finding": {"name": "x"}},
                                 {"finding": {"name": "organizations/1/sources/2/findings/3"}}])
def test_parse_rejects_bad_payloads(bad):
    with pytest.raises(ParseError):
        parse_notification(bad)


def test_decode_envelope_roundtrip():
    assert decode_pubsub_message(envelope({"a": 1})) == {"a": 1}
    with pytest.raises(ParseError):
        decode_pubsub_message({"message": {}})


# ---- dedup ----
def test_dedup_key_stable_across_finding_ids_and_time():
    a = parse_notification(make_payload(finding="f1", event_time="2026-10-05T10:00:00Z"))
    b = parse_notification(make_payload(finding="f2", event_time="2026-10-06T10:00:00Z"))
    c = parse_notification(make_payload(resource="//storage.googleapis.com/buckets/other"))
    assert dedup_key(a) == dedup_key(b) != dedup_key(c)


# ---- enrichment ----
def test_enrich_known_project_and_unknown_project():
    e = enrich(parse_notification(make_payload()))
    assert (e.owner_team, e.environment, e.is_publicly_exposed, e.data_sensitivity) == \
           ("T051", "production", True, "sensitive")
    e2 = enrich(parse_notification(make_payload(project="mystery", labels={})))
    assert e2.routed_to_review_queue and e2.owner_team == "SECURITY_REVIEW"


def test_enrich_label_mapping():
    e = enrich(parse_notification(make_payload(project="shared", labels={"owner": "t151", "env": "Staging"})))
    assert e.owner_team == "T151" and e.environment == "staging"


# ---- scoring ----
def test_worked_example_is_p1_with_80_points():
    e = enrich(parse_notification(make_payload()))
    s = score("HIGH", e)
    assert (s.total, s.priority) == (80, "P1")
    assert len(s.reasons) == 4


@pytest.mark.parametrize("sev,pts,pri", [("MEDIUM", 20, "P4"), ("LOW", 10, "P4")])
def test_low_risk_is_p4(sev, pts, pri):
    e = enrich(parse_notification(make_payload(category="OTHER", project="t251-dev", labels={})))
    s = score(sev, e)
    assert (s.total, s.priority) == (pts, pri)


def test_age_and_recurrence_capped():
    e = enrich(parse_notification(make_payload(category="OTHER", project="t251-dev", labels={})))
    s = score("MEDIUM", e, age_days=400, recurrence_count=99)
    assert s.total == 20 + 5 + 5


def test_due_dates_skip_weekends():
    fri = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)
    assert add_business_days(fri, 3).weekday() == 2  # Wednesday
    assert due_date("P1", fri).date() == fri.date()
    assert due_date("P2", fri).date().isoformat() == "2026-10-14"


# ---- workflow ----
def test_transitions():
    check_transition(S.ASSIGNED, S.IN_REMEDIATION)
    with pytest.raises(TransitionError):
        check_transition(S.NEW, S.RESOLVED)
    with pytest.raises(TransitionError):
        check_transition(S.NEW, S.MUTED)  # reason required
    with pytest.raises(TransitionError):
        check_transition(S.NEW, S.ACCEPTED_RISK, reason="ok")  # expiry required
    check_transition(S.NEW, S.ACCEPTED_RISK, reason="ok", expires_at="2027-01-01")


# ---- processor ----
def test_new_p1_creates_case_and_notifies(processor, notifier):
    r = processor.process(parse_notification(make_payload()))
    case = processor.store.get(r.finding_uid)
    assert r.action == "created"
    assert (case.calculated_priority, case.owner_team, case.workflow_state) == ("P1", "T051", S.ASSIGNED)
    assert notifier.sent == [(case.finding_uid, "new finding")]
    assert processor.store.audit_for(case.finding_uid)[0]["action"] == "created"


def test_unowned_goes_to_review_queue_as_new(processor):
    r = processor.process(parse_notification(make_payload(project="mystery", labels={})))
    case = processor.store.get(r.finding_uid)
    assert case.owner_team == "SECURITY_REVIEW" and case.workflow_state is S.NEW


def test_redelivered_event_is_ignored(processor, notifier):
    f = parse_notification(make_payload())
    processor.process(f)
    assert processor.process(f).action == "duplicate_event"
    assert len(notifier.sent) == 1


def test_repeat_notification_only_touches_last_seen(processor, notifier):
    processor.process(parse_notification(make_payload(event_time="2026-10-05T10:00:00Z")))
    r = processor.process(parse_notification(make_payload(event_time="2026-10-06T10:00:00Z")))
    c = processor.store.get(r.finding_uid)
    assert r.action == "updated" and c.last_seen_at.day == 6 and c.first_seen_at.day == 5
    assert len(processor.store.list()) == 1 and len(notifier.sent) == 1


def test_severity_increase_to_p1_renotifies(processor, notifier):
    kw = dict(project="t051-production", labels={"data-classification": "sensitive"})
    processor.process(parse_notification(make_payload(severity="LOW", event_time="2026-10-05T10:00:00Z", **kw)))
    assert notifier.sent == []  # LOW: 10+20+15+15 = 60 -> P2, digest only
    r = processor.process(parse_notification(make_payload(severity="HIGH", event_time="2026-10-06T10:00:00Z", **kw)))
    c = processor.store.get(r.finding_uid)
    assert r.action == "severity_increased" and c.calculated_priority == "P1"
    assert len(notifier.sent) == 1


def test_inactive_moves_to_pending_verification_then_recurrence(processor):
    processor.process(parse_notification(make_payload(event_time="2026-10-05T10:00:00Z")))
    r = processor.process(parse_notification(make_payload(state="INACTIVE", event_time="2026-10-06T10:00:00Z")))
    case = processor.store.get(r.finding_uid)
    assert r.action == "pending_verification" and case.workflow_state is S.PENDING_VERIFICATION
    case.workflow_state = S.RESOLVED  # verified
    processor.store.save(case)
    r2 = processor.process(parse_notification(make_payload(event_time="2026-10-09T10:00:00Z")))
    again = processor.store.get(r2.finding_uid)
    assert r2.action == "recurrence" and again.recurrence_count == 1
    assert again.finding_uid != case.finding_uid and len(processor.store.list()) == 2


def test_mute_rule_suppresses_notification(notifier):
    from app.processor import Processor
    rule = {"category": "PUBLIC_BUCKET_ACL", "resource_pattern": "*buckets/b1", "reason": "test bucket"}
    p = Processor(InMemoryStore(mute_rules=[rule]), notifier)
    r = p.process(parse_notification(make_payload()))
    assert r.action == "muted" and p.store.get(r.finding_uid).workflow_state is S.MUTED
    assert notifier.sent == []


# ---- HTTP ----
@pytest.fixture
def client(processor):
    return TestClient(build_app(processor))


def test_push_endpoint_and_bad_message(client):
    r = client.post("/pubsub/push", json=envelope(make_payload()))
    assert r.status_code == 200 and r.json()["action"] == "created"
    assert client.post("/pubsub/push", json={"message": {"data": "!!"}}).status_code == 400


def test_api_flow(client):
    uid = client.post("/pubsub/push", json=envelope(make_payload())).json()["finding_uid"]
    assert [f["finding_uid"] for f in client.get("/api/v1/findings?owner_team=T051").json()] == [uid]
    assert client.get("/api/v1/findings?owner_team=T151").json() == []

    assert client.patch(f"/api/v1/findings/{uid}/status", json={"state": "RESOLVED"}).status_code == 409
    ok = client.patch(f"/api/v1/findings/{uid}/status", json={"state": "IN_REMEDIATION"},
                      headers={"X-Goog-Authenticated-User-Email": "accounts.google.com:dev@x.com"})
    assert ok.status_code == 200
    assert client.patch(f"/api/v1/findings/{uid}/assignee", json={"assignee": "dev"}).json()["assignee"] == "dev"
    assert client.post(f"/api/v1/findings/{uid}/comments", json={"text": "on it"}).status_code == 201

    detail = client.get(f"/api/v1/findings/{uid}").json()
    actions = [a["action"] for a in detail["audit_trail"]]
    assert actions == ["created", "status_change", "assigned", "comment"]
    assert detail["audit_trail"][1]["actor"] == "dev@x.com"
    assert client.get("/api/v1/findings/nope").status_code == 404


def test_sla_breaches_report(client, processor):
    uid = client.post("/pubsub/push", json=envelope(make_payload(event_time="2020-01-01T00:00:00Z"))).json()["finding_uid"]
    assert [b["finding_uid"] for b in client.get("/api/v1/reports/sla-breaches").json()] == [uid]
