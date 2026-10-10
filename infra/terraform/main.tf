terraform {
  required_version = ">= 1.5"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  apis = [
    "securitycenter.googleapis.com", "pubsub.googleapis.com", "run.googleapis.com",
    "firestore.googleapis.com", "bigquery.googleapis.com", "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------------- Service accounts (least privilege) ----------------
resource "google_service_account" "processor" {
  account_id   = "scc-triage-processor"
  display_name = "SCC triage processor"
}

resource "google_service_account" "notifier" {
  account_id   = "scc-notifier"
  display_name = "SCC notifier"
}

resource "google_service_account" "dashboard" {
  account_id   = "dashboard-reader"
  display_name = "Dashboard reader"
}

resource "google_project_iam_member" "processor_roles" {
  for_each = toset(["roles/datastore.user", "roles/pubsub.subscriber"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_bigquery_dataset_iam_member" "processor_bq" {
  dataset_id = google_bigquery_dataset.triage.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_bq_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "notifier_firestore" {
  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.notifier.email}"
}

resource "google_bigquery_dataset_iam_member" "dashboard_view" {
  dataset_id = google_bigquery_dataset.triage.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dashboard.email}"
}

resource "google_project_iam_member" "dashboard_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dashboard.email}"
}

# ---------------- Secrets ----------------
resource "google_secret_manager_secret" "slack_webhook" {
  secret_id = "slack-webhook-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}
# Add the value out of band: gcloud secrets versions add slack-webhook-url --data-file=-

resource "google_secret_manager_secret_iam_member" "processor_slack" {
  secret_id = google_secret_manager_secret.slack_webhook.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.processor.email}"
}

# ---------------- Pub/Sub ----------------
resource "google_pubsub_topic" "ingest" {
  name       = "scc-findings-ingest"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "dlq" {
  name = "scc-findings-dlq"
}

resource "google_pubsub_subscription" "dlq_pull" {
  name                 = "scc-findings-dlq-sub"
  topic                = google_pubsub_topic.dlq.id
  ack_deadline_seconds = 60
}

resource "google_pubsub_subscription" "processor" {
  name                 = "scc-triage-processor-sub"
  topic                = google_pubsub_topic.ingest.id
  ack_deadline_seconds = 60

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.processor.uri}/pubsub/push"
    oidc_token {
      service_account_email = google_service_account.processor.email
      audience              = google_cloud_run_v2_service.processor.uri
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }
}

# Pub/Sub's service agent must be able to publish to the DLQ and ack from the source subscription.
data "google_project" "this" {}

locals {
  pubsub_agent = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.dlq.id
  role   = "roles/pubsub.publisher"
  member = local.pubsub_agent
}

resource "google_pubsub_subscription_iam_member" "dlq_subscriber" {
  subscription = google_pubsub_subscription.processor.id
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_agent
}

# ---------------- SCC continuous export ----------------
resource "google_scc_notification_config" "to_pubsub" {
  config_id    = "scc-triage-export"
  organization = var.org_id
  description  = "Export new and updated findings to the triage hub"
  pubsub_topic = google_pubsub_topic.ingest.id
  streaming_config {
    filter = var.scc_notification_filter
  }
}
# The SCC service account for the notification config needs roles/pubsub.publisher on the topic;
# Terraform exposes it as google_scc_notification_config.to_pubsub.service_account.
resource "google_pubsub_topic_iam_member" "scc_publisher" {
  topic  = google_pubsub_topic.ingest.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_scc_notification_config.to_pubsub.service_account}"
}

# ---------------- Firestore ----------------
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]
}

# Needed by FirestoreStore.get_by_dedup (equality + order_by).
resource "google_firestore_index" "findings_dedup" {
  collection = "findings"
  fields {
    field_path = "dedup_key"
    order      = "ASCENDING"
  }
  fields {
    field_path = "first_seen_at"
    order      = "DESCENDING"
  }
  depends_on = [google_firestore_database.default]
}

# ---------------- BigQuery ----------------
resource "google_bigquery_dataset" "triage" {
  dataset_id                 = "scc_triage"
  location                   = var.bq_location
  delete_contents_on_destroy = false
  depends_on                 = [google_project_service.apis]
}
# Tables are created from bigquery/schemas.sql (run once with `bq query --use_legacy_sql=false`).
# The SCC continuous export to BigQuery is configured separately (scc_findings_raw / its own dataset)
# because it is a per-organisation setting managed in SCC.

# ---------------- Cloud Run ----------------
resource "google_cloud_run_v2_service" "processor" {
  name     = "scc-triage-processor"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.processor.email
    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
    containers {
      image = var.processor_image
      env {
        name  = "BQ_DATASET"
        value = "${var.project_id}.${google_bigquery_dataset.triage.dataset_id}"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name = "SLACK_WEBHOOK_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.slack_webhook.secret_id
            version = "latest"
          }
        }
      }
    }
  }
  depends_on = [google_project_service.apis, google_secret_manager_secret_iam_member.processor_slack]
}

# Only the processor identity (used by the Pub/Sub push OIDC token) may invoke the service.
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  name     = google_cloud_run_v2_service.processor.name
  location = google_cloud_run_v2_service.processor.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.processor.email}"
}
