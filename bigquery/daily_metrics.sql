-- Scheduled query (daily). Builds today's per-team metrics from the latest
-- case snapshots. Run with @run_date as the target date.
MERGE `PROJECT.scc_triage.team_metrics_daily` T
USING (
  WITH latest AS (
    SELECT * EXCEPT (rn) FROM (
      SELECT c.*, ROW_NUMBER() OVER (PARTITION BY finding_uid ORDER BY snapshot_time DESC) rn
      FROM `PROJECT.scc_triage.triage_cases` c
      WHERE DATE(snapshot_time) <= @run_date
    ) WHERE rn = 1
  )
  SELECT
    @run_date AS date,
    owner_team AS team,
    COUNTIF(DATE(first_seen_at) = @run_date) AS new_findings,
    COUNTIF(DATE(resolved_at) = @run_date) AS resolved_findings,
    COUNTIF(severity = 'CRITICAL' AND state NOT IN ('RESOLVED','MUTED','ACCEPTED_RISK')) AS open_critical,
    COUNTIF(severity = 'HIGH' AND state NOT IN ('RESOLVED','MUTED','ACCEPTED_RISK')) AS open_high,
    COUNTIF(state NOT IN ('RESOLVED','MUTED','ACCEPTED_RISK') AND due_date < TIMESTAMP(@run_date)) AS overdue_findings,
    AVG(IF(resolved_at IS NOT NULL, TIMESTAMP_DIFF(resolved_at, first_seen_at, MINUTE) / 60.0, NULL)) AS mean_time_to_remediate_h
  FROM latest
  GROUP BY owner_team
) S
ON T.date = S.date AND T.team = S.team
WHEN MATCHED THEN UPDATE SET
  new_findings = S.new_findings, resolved_findings = S.resolved_findings,
  open_critical = S.open_critical, open_high = S.open_high,
  overdue_findings = S.overdue_findings,
  mean_time_to_remediate_h = S.mean_time_to_remediate_h
WHEN NOT MATCHED THEN INSERT ROW;
