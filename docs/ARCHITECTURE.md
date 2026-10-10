# Architecture: SCC Triage Hub

Event-driven and serverless. SCC detects findings and publishes them to Pub/Sub; a Cloud Run service deduplicates, enriches, scores and routes them; Firestore holds workflow state; BigQuery holds analytics; Looker Studio presents dashboards.

```text
 T051 GCP          T151 GCP          T251 GCP
    \                 |                 /
     +----------------+----------------+
                      v
        Security Command Center (findings)
                      |  continuous export / notification
                      v
          Pub/Sub  scc-findings-ingest ---> (fail x5) ---> scc-findings-dlq
                      |
                      v
        Cloud Run: Triage Processor
        parse > dedup > enrich > score > assign > persist > notify > audit
              |                          |                |
              v                          v                v
        Firestore (workflow)     BigQuery (analytics)   Slack / email
                                         |
                                         v
                                  Looker Studio
```

## 1. Components

### 1.1 SCC layer
Source of findings. Enable SCC for the org/folder/projects, create a continuous export to Pub/Sub (real-time triage) and a separate one to BigQuery (history and analytics). Use SCC filters to keep irrelevant categories out of the export.

Limitation: exports carry only new or updated findings; existing findings are not backfilled.

### 1.2 Pub/Sub layer
- Topic `scc-findings-ingest`; subscription `scc-triage-processor-sub` (push to Cloud Run, OIDC-authenticated).
- Dead-letter topic `scc-findings-dlq`; exponential backoff, max 5 delivery attempts.

### 1.3 Triage processor (Cloud Run, Python/FastAPI)
1. Receive the Pub/Sub push message.
2. Validate and parse the SCC payload.
3. Idempotency check on `finding name + event time`.
4. Build the dedup key.
5. Look up an existing case.
6. Enrich with ownership and environment.
7. Score risk.
8. Create or update the triage case.
9. Notify or escalate.
10. Write an audit event.

Min instances 0. Attached service account only; no long-lived keys.

### 1.4 Deduplication
```text
dedup_key = sha256(source_id | category | resource_name)
```
- Key unknown: create a new case.
- Key known, severity and state unchanged: update `last_seen_at` only.
- Severity increased: recalculate priority and re-notify.
- State became inactive: move to *Pending verification*.
- Recurs after closure: reopen as a linked recurrence case with `recurrence_count + 1`.

### 1.5 Enrichment
Inputs: finding payload, resource metadata, project/folder hierarchy, ownership mapping (`config/team_mappings.yaml`), resource labels (`environment`, `owner`, `application`, `data-classification`).
Outputs: `owning_team`, `environment`, `application_name`, `data_sensitivity`, `is_publicly_exposed`, `business_criticality`, `recommended_action`.

### 1.6 Risk scoring
`RiskScore = Severity + Exposure + DataSensitivity + Criticality + Age + Recurrence`

| Factor | Max points |
|---|---:|
| SCC severity | 40 |
| Public exposure | 20 |
| Sensitive data | 15 |
| Business criticality | 15 |
| Finding age | 5 |
| Recurrence | 5 |

| Score | Priority |
|---:|---|
| 80-100 | P1 |
| 60-79 | P2 |
| 35-59 | P3 |
| 0-34 | P4 |

Every score carries `risk_reasons[]` so the UI can explain it. Weights live in `config/scoring.yaml`.

### 1.7 Workflow store (Firestore)
Collections: `findings`, `team_mappings`, `mute_rules`, `audit_events`. See [`SCHEMA.md`](SCHEMA.md).

### 1.8 BigQuery analytics
Tables `scc_findings_raw`, `triage_cases`, `triage_events`, `team_metrics_daily`; DDL in [`bigquery/schemas.sql`](../bigquery/schemas.sql). Daily aggregates come from scheduled queries ([`bigquery/daily_metrics.sql`](../bigquery/daily_metrics.sql)).

### 1.9 Dashboards (Looker Studio)
Executive overview, team view, finding explorer, noise analysis, risk trend.

### 1.10 Notifications
| Event | Channel | Audience |
|---|---|---|
| New P1 | Slack + email | Security lead, owning team |
| New P2 | Daily digest | Owning team |
| P1 overdue | Slack + email | Security lead, team manager |
| P2 overdue | Daily digest | Owning team |
| Finding muted | Audit log + weekly report | Security lead |
| Accepted risk nearing expiry | Email | Risk owner, security lead |

### 1.11 Audit and governance
Every state change records actor, action, timestamp, old/new state, reason, finding ID, and evidence link. Accepted-risk records add justification, approver, compensating controls, expiry, and review frequency.

## 2. Worked example: public bucket in T051
1. SCC raises `PUBLIC_BUCKET_ACL` (High) for a T051 production bucket and exports it.
2. Pub/Sub pushes it to the processor.
3. Enrichment: owner T051, production, sensitive, public.
4. Score: 30 + 20 + 15 + 15 = **80, P1**.
5. Case created for T051, due same day; Slack + email sent; event written to BigQuery.
6. T051 fixes the bucket; SCC marks the finding inactive; case moves to *Pending verification*, then *Resolved*.

## 3. Security and IAM

| Service account | Roles |
|---|---|
| `scc-triage-processor` | `pubsub.subscriber`, `datastore.user`, `bigquery.dataEditor` (triage dataset), `secretmanager.secretAccessor` |
| `scc-notifier` | Secret accessor (Slack/email), `datastore.viewer` |
| `dashboard-reader` | `bigquery.dataViewer`, `bigquery.jobUser` |
| `scc-export-manager` | `securitycenter.notificationConfigsEditor` |

Principles: least privilege, no Owner/Editor, one service account per function, secrets in Secret Manager, Cloud Audit Logs on, Google-managed encryption (CMEK only if policy demands).

## 4. API

| Method | Endpoint | Status |
|---|---|---|
| POST | `/pubsub/push` | Implemented (ingestion) |
| GET | `/api/v1/findings` | Implemented |
| GET | `/api/v1/findings/{finding_uid}` | Implemented |
| PATCH | `/api/v1/findings/{finding_uid}/status` | Implemented |
| PATCH | `/api/v1/findings/{finding_uid}/assignee` | Implemented |
| POST | `/api/v1/findings/{finding_uid}/comments` | Implemented |
| GET | `/api/v1/reports/sla-breaches` | Implemented |
| POST | `/api/v1/findings/{finding_uid}/mute-request` | Planned (Release 2) |
| POST | `/api/v1/findings/{finding_uid}/accept-risk` | Planned (Release 3) |
| GET | `/api/v1/teams/{team}/metrics` | Planned (Release 2) |

## 5. Key decisions

| Decision | Choice | Why |
|---|---|---|
| Transport | Pub/Sub | Near-real-time SCC notifications; absorbs bursts |
| Processing | Cloud Run | Serverless, scales to zero |
| Workflow storage | Firestore | Simple document model, fast to build |
| Analytics | BigQuery | Native SCC export, strong SQL |
| Visualisation | Looker Studio | Low-cost, native BigQuery connector |
| Noise control | SCC mute rules + app-level suppression | Auditable and reduces load |
| Premium features | Deferred | Avoids budget-approval bottleneck |
