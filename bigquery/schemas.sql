-- Replace `PROJECT.scc_triage` with your project and dataset.
-- scc_findings_raw is typically populated by the SCC continuous BigQuery export;
-- this DDL is for the processor's own copy of normalised events.

CREATE SCHEMA IF NOT EXISTS `PROJECT.scc_triage`
OPTIONS (location = 'EU', default_table_expiration_days = NULL);

CREATE TABLE IF NOT EXISTS `PROJECT.scc_triage.scc_findings_raw` (
  event_time     TIMESTAMP NOT NULL,
  source_id      STRING    NOT NULL,
  finding_id     STRING    NOT NULL,
  finding        JSON,
  resource       JSON,
  project_id     STRING,
  ingestion_time TIMESTAMP NOT NULL
)
PARTITION BY DATE(event_time)
CLUSTER BY source_id, finding_id;

CREATE TABLE IF NOT EXISTS `PROJECT.scc_triage.triage_cases` (
  finding_uid       STRING NOT NULL,
  dedup_key         STRING NOT NULL,
  category          STRING,
  severity          STRING,
  current_priority  STRING,
  risk_score        INT64,
  owner_team        STRING,
  assignee          STRING,
  state             STRING,
  project_id        STRING,
  resource_name     STRING,
  first_seen_at     TIMESTAMP,
  last_seen_at      TIMESTAMP,
  due_date          TIMESTAMP,
  resolved_at       TIMESTAMP,
  recurrence_count  INT64,
  sla_breached      BOOL,
  snapshot_time     TIMESTAMP NOT NULL
)
PARTITION BY DATE(snapshot_time)
CLUSTER BY owner_team, current_priority;

CREATE TABLE IF NOT EXISTS `PROJECT.scc_triage.triage_events` (
  event_id    STRING NOT NULL,
  finding_uid STRING NOT NULL,
  event_type  STRING NOT NULL,
  actor       STRING,
  timestamp   TIMESTAMP NOT NULL,
  metadata    JSON
)
PARTITION BY DATE(timestamp)
CLUSTER BY finding_uid;

CREATE TABLE IF NOT EXISTS `PROJECT.scc_triage.team_metrics_daily` (
  date                     DATE   NOT NULL,
  team                     STRING NOT NULL,
  new_findings             INT64,
  resolved_findings        INT64,
  open_critical            INT64,
  open_high                INT64,
  overdue_findings         INT64,
  mean_time_to_remediate_h FLOAT64
)
PARTITION BY date
CLUSTER BY team;
