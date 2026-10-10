# Product Requirements Document: SCC Triage Hub

A centralised Google Cloud Security Command Center (SCC) finding-triage and prioritisation platform for projects **T051, T151, and T251**.

## 1. Problem statement

Security findings are generated across multiple GCP projects, but a small security team cannot manually review every alert. Teams face duplicate findings, unclear ownership, inconsistent severity handling, delayed remediation, and difficulty distinguishing real risk from noise. SCC provides central visibility, but it needs an additional workflow layer to make findings actionable for a small team.

## 2. Goals

- Centralise security findings from all three project teams into one operational view.
- Reduce manual triage effort through deduplication, filtering, enrichment, and prioritisation.
- Ensure every actionable finding has an owner, priority, status, and remediation deadline.
- Provide management dashboards showing open findings, ageing, team workload, and remediation trends.
- Operate primarily with Standard/free-tier SCC capabilities and avoid dependence on Premium-only features.

## 3. Non-goals

- No automatic remediation of production resources in the first release.
- Does not replace SCC; it extends SCC with triage workflow and reporting.
- No full SIEM, forensic investigation, or incident-response case management in version 1.
- No SCC Premium/Enterprise features unless separately approved.

## 4. Target users

| User | Need |
|---|---|
| Security analyst | Quickly identify the most important findings and decide next action |
| Project team / developer | Receive assigned findings with enough context to fix them |
| Security lead | Track backlog, SLA breaches, and repeat risks |
| Programme manager | View team progress, dashboard adoption, and delivery status |

## 5. Functional requirements

### FR-1: Central finding ingestion
- SCC continuous export publishes new/updated findings to a central Pub/Sub topic.
- The ingestion service parses the SCC notification payload.
- Retain source project, finding ID, category, severity, state, resource name, event time, and raw payload.
- Target: notifications processed within minutes.

### FR-2: Deduplication and noise reduction
- Generate a stable deduplication key from finding source, category, resource name, and relevant attributes.
- Suppress repeated notifications for an already open finding unless severity, state, or risk context changes.
- Support mute recommendations for false positives, accepted risks, test/non-production resources, and known exceptions.
- SCC mute rules retain an audit trail while tailoring findings to the organisation's risk model.

### FR-3: Finding enrichment
- Owning team (T051, T151, T251), environment (production, staging, development, test).
- Resource type, project, labels, and exposure information where available.
- Data sensitivity classification if configured.
- Human-readable summary and recommended first action.

### FR-4: Risk-based prioritisation
Score considers SCC severity, public exposure, data sensitivity, resource criticality, finding age, repeat occurrence, and exploitability metadata where available.

| Priority | Meaning | Initial response target |
|---|---|---|
| P1 | Immediate security risk | Same day |
| P2 | Important risk requiring scheduled remediation | 3 working days |
| P3 | Standard backlog item | 7 working days |
| P4 | Low-risk or informational | Next review cycle |

### FR-5: Ownership and assignment
- Configuration maps project, folder, resource type, label, or service name to an owning team.
- Undeterminable ownership routes to a security-review queue.
- Store assignee, assignment time, status, and due date.
- Analysts can reassign manually.

### FR-6: Triage workflow
States: **New**, **Triaging**, **Assigned**, **In remediation**, **Pending verification**, **Resolved**, **Accepted risk** (reason, owner, expiry required), **Muted / false positive** (justification required).

The platform preserves every state transition in its own workflow database.

### FR-7: Notifications and escalation
- P1 findings go immediately to the security team and owning team.
- Daily digests for P2 and P3.
- Escalate overdue P1 and P2 findings.
- Slack, email, or ticketing by configuration.
- Each notification includes title, severity, priority, project, resource, owner, recommendation, and SCC deep link.

### FR-8: Reporting and dashboards
- Open findings by severity, priority, team, project, and category.
- New versus resolved findings.
- Mean time to acknowledge and mean time to remediate.
- Findings older than SLA.
- Top recurring finding categories.
- Muted findings and accepted-risk register.
- Team workload distribution.

SCC continuous export to BigQuery stores each new finding and subsequent update as a separate row.

## 6. Non-functional requirements

| Requirement | Target |
|---|---|
| Ingestion latency | Process an SCC Pub/Sub notification within 5 minutes |
| Availability | 99% during programme hours |
| Data retention | At least 12 months in BigQuery |
| Security | Least-privilege IAM, encrypted storage, no secrets in code |
| Auditability | Every triage decision, assignment, mute, and closure logged |
| Scalability | Handle spikes in findings without message loss |
| Cost | Prefer serverless components; avoid Premium SCC dependencies |

## 7. Success metrics

- 90% of P1 findings acknowledged within 4 working hours.
- 80% of P2 findings assigned within 1 working day.
- 30% reduction in manually reviewed duplicate/low-value findings.
- 100% of open P1/P2 findings have an owner.
- Dashboard shows remediation trend weekly.
- No critical finding unassigned for more than one business day.

## 8. Assumptions and constraints

- The programme has SCC access for the relevant organisation, folder, or projects.
- Continuous export can be configured to Pub/Sub and/or BigQuery.
- Continuous export does **not** backfill: only newly generated or updated findings enter the stream after the export is created.
- Premium SCC features require budget approval and are out of scope for v1.
- Teams must provide resource ownership metadata or accept default routing rules.

## 9. Release plan

| Release | Scope |
|---|---|
| MVP | SCC to Pub/Sub ingestion, finding storage, basic priority scoring, Slack/email alerts, BigQuery export |
| Release 2 | Team ownership mapping, assignment workflow, mute recommendations, dashboards |
| Release 3 | SLA escalation, accepted-risk workflow, automated remediation suggestions, ticketing integration |
| Future | SOAR integration, attack-path context, automated safe remediation for selected finding types |

## 10. Team-wise plan

| Team | Scope | Deliverables |
|---|---|---|
| **T051** | Ingestion and triage engine | SCC notification config; Pub/Sub topic, subscription, DLQ; Cloud Run processor; parser; dedup; risk scoring; unit tests |
| **T151** | Ownership, workflow, notifications | Ownership mapping; workflow schema; assignment APIs; Slack/email notifier; SLA scheduler and escalation; audit logging |
| **T251** | Analytics, dashboard, reporting | BigQuery dataset and schemas; export config; daily-metrics queries; Looker Studio dashboards; SLA/ageing/recurrence/workload reports; data-quality checks |

## 11. Milestones

| Milestone | Duration | Output |
|---|---:|---|
| M1: Requirements and design | Week 1 | Final PRD, architecture diagram, IAM plan |
| M2: Infrastructure setup | Week 2 | GCP project setup, Pub/Sub, BigQuery, service accounts |
| M3: Ingestion MVP | Week 3 | SCC to Pub/Sub to processor to database |
| M4: Triage workflow | Week 4 | Priority scoring, ownership, assignment, notifications |
| M5: Dashboards | Week 5 | BigQuery models and Looker Studio dashboards |
| M6: Testing and hardening | Week 6 | Load test, failure tests, IAM review, documentation |
| M7: Demo and handover | Week 7 | Working demo, runbook, final report |
