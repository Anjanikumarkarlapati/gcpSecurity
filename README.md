# SCC Triage Hub

Centralised Google Cloud Security Command Center (SCC) finding triage for projects **T051, T151 and T251**: SCC findings flow through Pub/Sub into a Cloud Run processor that deduplicates, enriches, scores (P1-P4), assigns an owner and SLA, notifies, and feeds BigQuery/Looker Studio.

| Doc | What |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Requirements, users, metrics, release plan, team split, milestones |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, scoring, IAM, API, decisions |
| [docs/SCHEMA.md](docs/SCHEMA.md) | Firestore collections and workflow state machine |

## Layout

```text
config/                      Ownership mappings and scoring weights (YAML)
services/triage_processor/   Cloud Run service (FastAPI) + tests
bigquery/                    Table DDL and the daily-metrics scheduled query
infra/terraform/             Pub/Sub, DLQ, SCC export, Firestore, BigQuery, IAM, Cloud Run
```

## Run the tests

```bash
cd services/triage_processor
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Run locally (no GCP needed)

```bash
cd services/triage_processor
STORE=memory RUN_SERVER=1 uvicorn app.main:app --reload
```

Post a sample SCC notification (wrapped in a Pub/Sub push envelope) to `/pubsub/push`, then `GET /api/v1/findings`.

## Deploy

1. `docker build -f services/triage_processor/Dockerfile -t <image> .` (from the repo root) and push to Artifact Registry.
2. `cd infra/terraform && terraform init && terraform apply -var-file=my.tfvars` (see `example.tfvars`).
3. Create the tables: run `bigquery/schemas.sql` (replace `PROJECT`).
4. Add the Slack webhook: `gcloud secrets versions add slack-webhook-url --data-file=-`.
5. Edit `config/team_mappings.yaml` for your real project IDs/labels and rebuild the image.

## Status

Implemented: ingestion, parsing, dedup, enrichment, scoring, SLA dates, workflow state machine, mute rules, audit trail, P1 Slack alerts, triage API, BigQuery sink, schemas, Terraform.

Not yet built: daily digests and overdue escalation job (T151), email/ticketing notifiers, mute-request / accept-risk / team-metrics endpoints, periodic re-scoring for finding age, Looker Studio dashboards (T251), SCC-to-BigQuery export setup (org-level).
