from __future__ import annotations

from . import config
from .models import Enrichment, Finding

_ACTIONS = {
    "PUBLIC_BUCKET_ACL": "Remove the public IAM binding or enable uniform bucket-level access with least-privilege IAM.",
    "OPEN_FIREWALL": "Restrict the firewall rule source ranges to required CIDRs.",
    "PUBLIC_IP_ADDRESS": "Remove the external IP or place the instance behind a load balancer or IAP.",
    "PUBLIC_SQL_INSTANCE": "Disable public IP and use private connectivity or authorised networks.",
}
_DEFAULT_ACTION = "Review the finding in SCC, confirm the affected resource and apply the remediation guidance."


def _labels(f: Finding) -> set[str]:
    return {f"{k}:{v}".lower() for k, v in f.labels.items()}


def enrich(f: Finding) -> Enrichment:
    cfg = config.load("team_mappings.yaml")
    labels = _labels(f)

    team, env = None, None
    for rule in cfg.get("team_mappings", []):
        if "project" in rule and rule["project"] == f.project_id:
            team, env = rule["team"], rule.get("environment")
            break
        if "label" in rule and rule["label"].lower() in labels:
            team, env = rule["team"], rule.get("environment")
            break

    review_queue = team is None
    team = team or cfg["default_team"]

    if env is None:
        for key in cfg.get("environment_labels", []):
            for k, v in f.labels.items():
                if k.lower() == key:
                    env = v.lower()
    env = env or "unknown"

    sensitive = any(l.lower() in labels for l in cfg.get("sensitive_labels", []))
    critical = any(l.lower() in labels for l in cfg.get("criticality_labels", []))
    public = f.category in cfg.get("public_finding_categories", [])

    return Enrichment(
        owner_team=team,
        environment=env,
        is_publicly_exposed=public,
        data_sensitivity="sensitive" if sensitive else "normal",
        high_criticality=critical or env == "production",
        recommended_action=_ACTIONS.get(f.category, _DEFAULT_ACTION),
        routed_to_review_queue=review_queue,
    )
