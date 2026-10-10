variable "project_id" {
  description = "Central security project that hosts the triage platform"
  type        = string
}

variable "org_id" {
  description = "GCP organisation ID that SCC is enabled on"
  type        = string
}

variable "region" {
  type    = string
  default = "europe-west2"
}

variable "bq_location" {
  type    = string
  default = "EU"
}

variable "processor_image" {
  description = "Container image for the triage processor (build from services/triage_processor)"
  type        = string
}

variable "scc_notification_filter" {
  description = "SCC filter for the Pub/Sub export. Drop noise categories here."
  type        = string
  default     = "state=\"ACTIVE\" OR state=\"INACTIVE\""
}
