import { Link } from "react-router-dom";
import { api, isOpen, STATE_LABEL } from "../api.js";
import { useAsync } from "../hooks.js";
import { PageHead } from "../components/Layout.jsx";
import { PriorityStatus } from "../components/Status.jsx";

function countBy(list, key) {
  const m = {};
  list.forEach((f) => { m[f[key]] = (m[f[key]] || 0) + 1; });
  return Object.entries(m).sort((a, b) => b[1] - a[1]);
}

function Bars({ rows, label }) {
  const max = Math.max(1, ...rows.map(([, n]) => n));
  if (!rows.length) return <p className="muted">Nothing to show.</p>;
  return (
    <ul className="bars" aria-label={label}>
      {rows.map(([name, n]) => (
        <li key={name}>
          <span className="bars-name">{name}</span>
          <span className="bars-track" aria-hidden="true">
            <span className="bars-fill" style={{ width: `${(n / max) * 100}%` }} />
          </span>
          <span className="bars-n">{n}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard() {
  const { data, error, loading } = useAsync(() => Promise.all([api.findings(), api.breaches()]));

  if (loading) return <p className="empty">Loading…</p>;
  if (error) return <div className="banner banner-critical" role="alert">Could not load findings: {error.message}</div>;

  const [all, breaches] = data;
  const open = all.filter(isOpen);
  const urgent = open.filter((f) => ["P1", "P2"].includes(f.calculated_priority));
  const unowned = open.filter((f) => f.owner_team === "SECURITY_REVIEW");
  const p1Unassigned = open.filter((f) => f.calculated_priority === "P1" && !f.assignee);
  const recurring = all.filter((f) => f.recurrence_count > 0);

  return (
    <>
      <PageHead
        eyebrow="Overview"
        title="Security findings"
        subtitle="Prioritised, owned and measured across T051, T151 and T251."
      />

      {unowned.length > 0 && (
        <div className="banner banner-warning" role="status">
          <strong>{unowned.length} finding{unowned.length > 1 ? "s" : ""} could not be matched to a team</strong>{" "}
          and sit in the security-review queue. <Link to="/findings?team=SECURITY_REVIEW">Review them</Link>.
        </div>
      )}

      <section className="bento">
        <div className="hero">
          <p className="eyebrow hero-eyebrow">Open P1 and P2</p>
          <p className="hero-number">{urgent.length}</p>
          <p className="hero-sub">
            {breaches.length} past SLA · {p1Unassigned.length} P1 without an assignee
          </p>
          <div className="hero-bars" aria-hidden="true">
            {[40, 65, 50, 85, 70, 100].map((h, i) => (
              <span key={i} style={{ height: `${h}%`, animationDelay: `${i * 80}ms` }} />
            ))}
          </div>
        </div>

        <div className="card tile">
          <div className="card-head"><h2>By priority</h2></div>
          <div className="card-body">
            {["P1", "P2", "P3", "P4"].map((p) => (
              <div className="row spread tile-row" key={p}>
                <PriorityStatus priority={p} />
                <Link to={`/findings?priority=${p}`} className="tile-n">
                  {open.filter((f) => f.calculated_priority === p).length}
                </Link>
              </div>
            ))}
          </div>
        </div>

        <div className="card tile">
          <div className="card-head"><h2>Team workload</h2></div>
          <div className="card-body">
            <Bars rows={countBy(open, "owner_team")} label="Open findings by team" />
          </div>
        </div>

        <div className="card tile">
          <div className="card-head"><h2>Workflow state</h2></div>
          <div className="card-body">
            <Bars
              rows={countBy(open, "workflow_state").map(([s, n]) => [STATE_LABEL[s] || s, n])}
              label="Open findings by state"
            />
          </div>
        </div>

        <div className="card tile">
          <div className="card-head"><h2>Top categories</h2></div>
          <div className="card-body">
            <Bars rows={countBy(open, "category").slice(0, 5)} label="Open findings by category" />
          </div>
        </div>

        <div className="card tile tile-wide">
          <div className="card-head"><h2>Past SLA</h2></div>
          <div className="card-body">
            <p className="tile-big">{breaches.length}</p>
            <p className="muted">
              {recurring.length} recurring finding{recurring.length === 1 ? "" : "s"} overall.
            </p>
            <Link to="/findings?tab=overdue" className="btn btn-sm">View overdue</Link>
          </div>
        </div>
      </section>
    </>
  );
}
