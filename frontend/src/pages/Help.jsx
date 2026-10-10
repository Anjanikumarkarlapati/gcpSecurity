import { PageHead } from "../components/Layout.jsx";
import { PriorityStatus } from "../components/Status.jsx";

export default function Help() {
  return (
    <>
      <PageHead eyebrow="Guide" title="How to use" subtitle="What the priorities mean and how a finding moves to resolved." />

      <section className="card">
        <div className="card-head"><h2>Priorities and response targets</h2></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Priority</th><th>Meaning</th><th>Respond within</th></tr></thead>
            <tbody>
              <tr><td><PriorityStatus priority="P1" /></td><td>Immediate security risk</td><td>Same day</td></tr>
              <tr><td><PriorityStatus priority="P2" /></td><td>Important, schedule remediation</td><td>3 working days</td></tr>
              <tr><td><PriorityStatus priority="P3" /></td><td>Standard backlog item</td><td>7 working days</td></tr>
              <tr><td><PriorityStatus priority="P4" /></td><td>Low risk or informational</td><td>Next review cycle</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <div className="card-head"><h2>Daily workflow</h2></div>
        <div className="card-body">
          <ol className="steps">
            <li>Start on the <strong>Dashboard</strong>. Clear anything in the security-review queue first.</li>
            <li>Open <strong>Findings</strong> and work from the top: the list is sorted by risk score.</li>
            <li>Open a finding. <strong>Why this priority?</strong> lists every factor behind the score.</li>
            <li>Assign it, then move it to <em>In remediation</em> when the owning team starts work.</li>
            <li>When SCC reports the finding inactive, it moves to <em>Pending verification</em>. Confirm the fix, then mark it <em>Resolved</em>.</li>
          </ol>
          <div className="advisory">
            <strong>Muting and accepting risk need a reason.</strong> Accepted risk also needs an expiry date.
            Every change is recorded in the finding's audit trail.
          </div>
        </div>
      </section>
    </>
  );
}
