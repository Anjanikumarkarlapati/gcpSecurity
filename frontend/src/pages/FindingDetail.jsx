import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { api, fmtDate, STATE_LABEL, TRANSITIONS } from "../api.js";
import { useAsync } from "../hooks.js";
import { PageHead } from "../components/Layout.jsx";
import { PriorityStatus, StateStatus } from "../components/Status.jsx";

function StatusForm({ f, onDone }) {
  const options = TRANSITIONS[f.workflow_state] || [];
  const [state, setState] = useState("");
  const [reason, setReason] = useState("");
  const [expires, setExpires] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const needsReason = ["MUTED", "ACCEPTED_RISK"].includes(state);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await api.setStatus(f.finding_uid, {
        state, reason: reason || null,
        expires_at: expires ? new Date(expires).toISOString() : null,
      });
      setState(""); setReason(""); setExpires("");
      onDone();
    } catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="stack">
      <label className="field">
        <span>Move to</span>
        <select className="input" value={state} onChange={(e) => setState(e.target.value)} required>
          <option value="">Choose a state…</option>
          {options.map((s) => <option key={s} value={s}>{STATE_LABEL[s]}</option>)}
        </select>
      </label>
      {needsReason && (
        <label className="field">
          <span>Reason (required)</span>
          <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} required />
        </label>
      )}
      {state === "ACCEPTED_RISK" && (
        <label className="field">
          <span>Expiry date (required)</span>
          <input className="input" type="date" value={expires} onChange={(e) => setExpires(e.target.value)} required />
        </label>
      )}
      {err && <div className="banner banner-critical" role="alert">{err}</div>}
      <button className="btn btn-primary" disabled={!state || busy}>Update state</button>
    </form>
  );
}

function AssignForm({ f, onDone }) {
  const [assignee, setAssignee] = useState(f.assignee || "");
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try { await api.setAssignee(f.finding_uid, { assignee }); onDone(); }
    catch (ex) { setErr(ex.message); }
  };
  return (
    <form onSubmit={submit} className="stack">
      <label className="field">
        <span>Assignee</span>
        <input className="input" value={assignee} onChange={(e) => setAssignee(e.target.value)} required />
      </label>
      {err && <div className="banner banner-critical" role="alert">{err}</div>}
      <button className="btn" disabled={!assignee}>Assign</button>
    </form>
  );
}

function CommentForm({ f, onDone }) {
  const [text, setText] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    await api.comment(f.finding_uid, text);
    setText(""); onDone();
  };
  return (
    <form onSubmit={submit} className="stack">
      <label className="field">
        <span>Triage note</span>
        <textarea className="input" rows={3} value={text} onChange={(e) => setText(e.target.value)} required />
      </label>
      <button className="btn" disabled={!text}>Add note</button>
    </form>
  );
}

export default function FindingDetail() {
  const { uid } = useParams();
  const { data: f, error, loading, reload } = useAsync(() => api.finding(uid), [uid]);

  if (loading && !f) return <p className="empty">Loading…</p>;
  if (error) return <div className="banner banner-critical" role="alert">{error.message}</div>;

  const late = new Date(f.due_date) < new Date() && !["RESOLVED", "MUTED", "ACCEPTED_RISK"].includes(f.workflow_state);

  return (
    <>
      <p><Link to="/findings" className="back"><ArrowLeft size={16} aria-hidden="true" /> All findings</Link></p>
      <PageHead mono eyebrow={f.finding_uid} title={f.category} subtitle={f.resource_name}>
        <div className="row"><PriorityStatus priority={f.calculated_priority} /><StateStatus state={f.workflow_state} /></div>
      </PageHead>

      {f.owner_team === "SECURITY_REVIEW" && (
        <div className="banner banner-warning">
          No owning team matched this finding. Assign it to a team or add a mapping in <code>config/team_mappings.yaml</code>.
        </div>
      )}
      {late && <div className="banner banner-critical" role="alert">This finding is past its SLA due date.</div>}

      <div className="grid-2">
        <div className="stack-lg">
          <section className="card">
            <div className="card-head"><h2>Why {f.calculated_priority}? Score {f.risk_score}/100</h2></div>
            <div className="card-body">
              <ul className="reasons">{f.risk_reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              <div className="advisory"><strong>Recommended action.</strong> {f.recommended_action}</div>
            </div>
          </section>

          <section className="card">
            <div className="card-head"><h2>Details</h2></div>
            <dl className="facts">
              <dt>Project</dt><dd>{f.project_id}</dd>
              <dt>Owner team</dt><dd>{f.owner_team}</dd>
              <dt>Assignee</dt><dd>{f.assignee || "Unassigned"}</dd>
              <dt>Environment</dt><dd>{f.environment}</dd>
              <dt>Severity</dt><dd>{f.severity}</dd>
              <dt>First seen</dt><dd>{fmtDate(f.first_seen_at)}</dd>
              <dt>Last seen</dt><dd>{fmtDate(f.last_seen_at)}</dd>
              <dt>Due</dt><dd className={late ? "late" : ""}>{fmtDate(f.due_date)}</dd>
              <dt>Recurrences</dt><dd>{f.recurrence_count}</dd>
            </dl>
          </section>

          <section className="card">
            <div className="card-head"><h2>Audit trail</h2></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Change</th><th>Reason</th></tr></thead>
                <tbody>
                  {f.audit_trail.map((a, i) => (
                    <tr key={i}>
                      <td>{fmtDate(a.timestamp)}</td><td>{a.actor}</td><td>{a.action}</td>
                      <td className="mono">{a.old_state || "-"} → {a.new_state || "-"}</td>
                      <td>{a.reason || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="stack-lg">
          <section className="card">
            <div className="card-head"><h2>Change state</h2></div>
            <div className="card-body">
              {(TRANSITIONS[f.workflow_state] || []).length
                ? <StatusForm f={f} onDone={reload} />
                : <p className="muted">No transitions available.</p>}
            </div>
          </section>
          <section className="card">
            <div className="card-head"><h2>Assignment</h2></div>
            <div className="card-body"><AssignForm f={f} onDone={reload} /></div>
          </section>
          <section className="card">
            <div className="card-head"><h2>Notes</h2></div>
            <div className="card-body stack">
              {f.triage_notes.length === 0 && <p className="muted">No notes yet.</p>}
              {f.triage_notes.map((n, i) => (
                <div key={i} className="note"><strong>{n.author}</strong> · {fmtDate(n.at)}<br />{n.text}</div>
              ))}
              <CommentForm f={f} onDone={reload} />
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
