# Firestore Schema

```text
findings/{finding_uid}
  dedup_key, source_id, finding_id, finding_name, project_id, resource_name,
  category, severity, state (SCC), workflow_state, calculated_priority,
  risk_score, risk_reasons[], owner_team, assignee, environment,
  first_seen_at, last_seen_at, due_date, recurrence_count, triage_notes[]

team_mappings/{mapping_id}
  project_id, folder_id, label_key, label_value, owning_team, environment

mute_rules/{rule_id}
  category, resource_pattern, reason, created_by, expires_at, approved_by

audit_events/{event_id}
  finding_uid, actor, action, old_state, new_state, timestamp, reason, evidence_url

processed_events/{event_id}     # idempotency ledger: sha256(finding_name|event_time)
```

## Workflow states and transitions

`NEW`, `TRIAGING`, `ASSIGNED`, `IN_REMEDIATION`, `PENDING_VERIFICATION`, `RESOLVED`, `ACCEPTED_RISK`, `MUTED`.

| From | Allowed to |
|---|---|
| NEW | TRIAGING, ASSIGNED, MUTED, ACCEPTED_RISK |
| TRIAGING | ASSIGNED, MUTED, ACCEPTED_RISK |
| ASSIGNED | IN_REMEDIATION, TRIAGING, MUTED, ACCEPTED_RISK |
| IN_REMEDIATION | PENDING_VERIFICATION, ASSIGNED, ACCEPTED_RISK |
| PENDING_VERIFICATION | RESOLVED, IN_REMEDIATION |
| RESOLVED | NEW (recurrence) |
| ACCEPTED_RISK | NEW (expiry), TRIAGING |
| MUTED | NEW, TRIAGING |

`MUTED` and `ACCEPTED_RISK` transitions require a reason. `ACCEPTED_RISK` also requires an expiry date.
