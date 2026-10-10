"""FastAPI entrypoint: Pub/Sub push ingestion plus the triage API.

Deploy with Cloud Run authentication required (no allUsers). The Pub/Sub push
subscription authenticates with an OIDC token; analysts reach /api via IAP or IAM.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from . import notifier as notifier_mod
from .models import WorkflowState
from .parser import ParseError, decode_pubsub_message, parse_notification
from .processor import Processor
from .store import FirestoreStore, InMemoryStore, case_to_dict
from .workflow import TransitionError, check_transition


def build_app(processor: Processor | None = None) -> FastAPI:
    if processor is None:
        store = FirestoreStore(os.environ.get("GOOGLE_CLOUD_PROJECT")) \
            if os.environ.get("STORE", "firestore") == "firestore" else InMemoryStore()
        sink = None
        if os.environ.get("BQ_DATASET"):
            from .sink import BigQuerySink
            sink = BigQuerySink(os.environ["BQ_DATASET"])
        processor = Processor(store, notifier_mod.from_env(), sink)

    app = FastAPI(title="SCC Triage Hub")
    store = processor.store

    def actor(email: Optional[str]) -> str:
        # IAP sets "accounts.google.com:user@example.com"
        return email.split(":")[-1] if email else "unknown"

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.post("/pubsub/push")
    async def pubsub_push(request: Request):
        try:
            finding = parse_notification(decode_pubsub_message(await request.json()))
        except (ParseError, ValueError) as e:
            # 400 => Pub/Sub retries, then routes to the dead-letter topic.
            raise HTTPException(400, str(e))
        r = processor.process(finding)
        return {"action": r.action, "finding_uid": r.finding_uid}

    # ---- triage API ----
    def get_or_404(uid: str):
        c = store.get(uid)
        if not c:
            raise HTTPException(404, "finding not found")
        return c

    @app.get("/api/v1/findings")
    def list_findings(owner_team: Optional[str] = None, calculated_priority: Optional[str] = None,
                      workflow_state: Optional[str] = None, project_id: Optional[str] = None):
        cases = store.list(owner_team=owner_team, calculated_priority=calculated_priority,
                           workflow_state=workflow_state, project_id=project_id)
        cases.sort(key=lambda c: (-c.risk_score, c.due_date))
        return [case_to_dict(c) for c in cases]

    @app.get("/api/v1/findings/{uid}")
    def get_finding(uid: str):
        d = case_to_dict(get_or_404(uid))
        d["audit_trail"] = store.audit_for(uid)
        return d

    class StatusIn(BaseModel):
        state: WorkflowState
        reason: Optional[str] = None
        expires_at: Optional[datetime] = None

    @app.patch("/api/v1/findings/{uid}/status")
    def set_status(uid: str, body: StatusIn, x_goog_authenticated_user_email: Optional[str] = Header(None)):
        c = get_or_404(uid)
        try:
            check_transition(c.workflow_state, body.state, body.reason,
                             body.expires_at.isoformat() if body.expires_at else None)
        except TransitionError as e:
            raise HTTPException(409, str(e))
        old = c.workflow_state
        c.workflow_state = body.state
        if body.state is WorkflowState.RESOLVED:
            c.resolved_at = datetime.now(timezone.utc)
        processor.store.save(c)
        processor._audit(uid, "status_change", old.value, body.state.value, body.reason,
                         actor=actor(x_goog_authenticated_user_email))
        return case_to_dict(c)

    class AssigneeIn(BaseModel):
        assignee: str
        owner_team: Optional[str] = None

    @app.patch("/api/v1/findings/{uid}/assignee")
    def set_assignee(uid: str, body: AssigneeIn, x_goog_authenticated_user_email: Optional[str] = Header(None)):
        c = get_or_404(uid)
        old = c.assignee or c.owner_team
        c.assignee = body.assignee
        if body.owner_team:
            c.owner_team = body.owner_team
        if c.workflow_state in (WorkflowState.NEW, WorkflowState.TRIAGING):
            c.workflow_state = WorkflowState.ASSIGNED
        store.save(c)
        processor._audit(uid, "assigned", old, body.assignee, actor=actor(x_goog_authenticated_user_email))
        return case_to_dict(c)

    class CommentIn(BaseModel):
        text: str

    @app.post("/api/v1/findings/{uid}/comments", status_code=201)
    def add_comment(uid: str, body: CommentIn, x_goog_authenticated_user_email: Optional[str] = Header(None)):
        c = get_or_404(uid)
        note = {"author": actor(x_goog_authenticated_user_email), "text": body.text,
                "at": datetime.now(timezone.utc).isoformat()}
        c.triage_notes.append(note)
        store.save(c)
        processor._audit(uid, "comment", reason=body.text, actor=note["author"])
        return note

    @app.get("/api/v1/reports/sla-breaches")
    def sla_breaches():
        now = datetime.now(timezone.utc)
        closed = {WorkflowState.RESOLVED, WorkflowState.MUTED, WorkflowState.ACCEPTED_RISK}
        out = [case_to_dict(c) for c in store.list()
               if c.workflow_state not in closed and c.due_date < now]
        return sorted(out, key=lambda d: d["due_date"])

    # Serve the built React UI (HashRouter, so no SPA fallback is needed).
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    ui = Path(os.environ.get("FRONTEND_DIR", "/srv/frontend"))
    if ui.is_dir():
        app.mount("/", StaticFiles(directory=ui, html=True), name="ui")

    return app


def _default_app():
    # Importing app.main under test must not need GCP credentials.
    return build_app() if os.environ.get("K_SERVICE") or os.environ.get("RUN_SERVER") else None


app = _default_app()
