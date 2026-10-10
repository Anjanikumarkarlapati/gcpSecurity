import { Link, useSearchParams } from "react-router-dom";
import { api, fmtDate, isOpen, shortResource } from "../api.js";
import { useAsync } from "../hooks.js";
import { PageHead } from "../components/Layout.jsx";
import { PriorityStatus, StateStatus } from "../components/Status.jsx";

const TABS = [
  ["open", "Open"],
  ["overdue", "Past SLA"],
  ["closed", "Closed"],
  ["all", "All"],
];

export default function Findings() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "open";
  const team = params.get("team") || "";
  const priority = params.get("priority") || "";
  const q = params.get("q") || "";

  const { data, error, loading } = useAsync(() => api.findings());

  const set = (k, v) => {
    const next = new URLSearchParams(params);
    v ? next.set(k, v) : next.delete(k);
    setParams(next, { replace: true });
  };

  if (loading) return <p className="empty">Loading…</p>;
  if (error) return <div className="banner banner-critical" role="alert">Could not load findings: {error.message}</div>;

  const now = Date.now();
  const teams = [...new Set(data.map((f) => f.owner_team))].sort();
  const rows = data.filter((f) => {
    if (tab === "open" && !isOpen(f)) return false;
    if (tab === "closed" && isOpen(f)) return false;
    if (tab === "overdue" && !(isOpen(f) && new Date(f.due_date) < now)) return false;
    if (team && f.owner_team !== team) return false;
    if (priority && f.calculated_priority !== priority) return false;
    if (q && !`${f.category} ${f.resource_name} ${f.project_id}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });

  return (
    <>
      <PageHead eyebrow="Triage" title="Findings" subtitle="Sorted by risk score, highest first." />

      <div className="tabs" role="tablist" aria-label="Finding views">
        {TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id}
            className={tab === id ? "tab active" : "tab"} onClick={() => set("tab", id === "open" ? "" : id)}>
            {label}
          </button>
        ))}
      </div>

      <div className="filters row">
        <label className="field">
          <span>Search</span>
          <input className="input" value={q} placeholder="Category, resource or project"
            onChange={(e) => set("q", e.target.value)} />
        </label>
        <label className="field">
          <span>Team</span>
          <select className="input" value={team} onChange={(e) => set("team", e.target.value)}>
            <option value="">All teams</option>
            {teams.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Priority</span>
          <select className="input" value={priority} onChange={(e) => set("priority", e.target.value)}>
            <option value="">All priorities</option>
            {["P1", "P2", "P3", "P4"].map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
      </div>

      <div className="card">
        {rows.length === 0 ? (
          <p className="empty">No findings match these filters.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Priority</th><th>Category</th><th>Resource</th><th>Team</th>
                  <th>State</th><th className="num">Score</th><th>Due</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((f) => {
                  const late = isOpen(f) && new Date(f.due_date) < now;
                  return (
                    <tr key={f.finding_uid}>
                      <td><PriorityStatus priority={f.calculated_priority} /></td>
                      <td>
                        <Link to={`/findings/${f.finding_uid}`}>{f.category}</Link>
                        <div className="muted mono">{f.finding_uid}</div>
                      </td>
                      <td><span className="mono" title={f.resource_name}>{shortResource(f.resource_name)}</span>
                        <div className="muted">{f.project_id}</div></td>
                      <td>{f.owner_team}</td>
                      <td><StateStatus state={f.workflow_state} /></td>
                      <td className="num">{f.risk_score}</td>
                      <td className={late ? "late" : ""}>{fmtDate(f.due_date)}{late && " (late)"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
