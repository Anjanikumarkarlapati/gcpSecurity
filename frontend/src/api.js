async function request(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* keep statusText */ }
    throw new Error(detail);
  }
  return res.json();
}

const send = (method, body) => ({ method, body: JSON.stringify(body) });

export const api = {
  findings: () => request("/api/v1/findings"),
  finding: (uid) => request(`/api/v1/findings/${uid}`),
  breaches: () => request("/api/v1/reports/sla-breaches"),
  setStatus: (uid, body) => request(`/api/v1/findings/${uid}/status`, send("PATCH", body)),
  setAssignee: (uid, body) => request(`/api/v1/findings/${uid}/assignee`, send("PATCH", body)),
  comment: (uid, text) => request(`/api/v1/findings/${uid}/comments`, send("POST", { text })),
};

export const CLOSED = ["RESOLVED", "MUTED", "ACCEPTED_RISK"];
export const isOpen = (f) => !CLOSED.includes(f.workflow_state);

export const STATE_LABEL = {
  NEW: "New", TRIAGING: "Triaging", ASSIGNED: "Assigned", IN_REMEDIATION: "In remediation",
  PENDING_VERIFICATION: "Pending verification", RESOLVED: "Resolved",
  ACCEPTED_RISK: "Accepted risk", MUTED: "Muted",
};

// Mirrors services/triage_processor/app/workflow.py
export const TRANSITIONS = {
  NEW: ["TRIAGING", "ASSIGNED", "MUTED", "ACCEPTED_RISK"],
  TRIAGING: ["ASSIGNED", "MUTED", "ACCEPTED_RISK"],
  ASSIGNED: ["IN_REMEDIATION", "TRIAGING", "MUTED", "ACCEPTED_RISK"],
  IN_REMEDIATION: ["PENDING_VERIFICATION", "ASSIGNED", "ACCEPTED_RISK"],
  PENDING_VERIFICATION: ["RESOLVED", "IN_REMEDIATION"],
  RESOLVED: ["NEW"],
  ACCEPTED_RISK: ["NEW", "TRIAGING"],
  MUTED: ["NEW", "TRIAGING"],
};

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "-";
export const shortResource = (r) => r.split("/").slice(-2).join("/");
