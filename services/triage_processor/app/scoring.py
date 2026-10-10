from __future__ import annotations

from datetime import datetime, timedelta

from . import config
from .models import Enrichment, Score

_BUSINESS_DAYS_FALLBACK_CALENDAR = 14


def score(severity: str, e: Enrichment, age_days: float = 0, recurrence_count: int = 0) -> Score:
    c = config.load("scoring.yaml")
    reasons: list[str] = []

    sev_pts = c["severity_points"].get(severity, 0)
    total = sev_pts
    reasons.append(f"{severity.title()} severity finding (+{sev_pts})")

    if e.is_publicly_exposed:
        total += c["exposure_public"]
        reasons.append(f"Publicly exposed resource (+{c['exposure_public']})")
    if e.data_sensitivity == "sensitive":
        total += c["sensitive_data"]
        reasons.append(f"Sensitive data classification (+{c['sensitive_data']})")
    if e.high_criticality:
        total += c["criticality_high"]
        reasons.append(f"High business criticality / production (+{c['criticality_high']})")

    age_pts = min(int(age_days // 7) * c["age_per_7_days"], c["age_max"])
    if age_pts:
        total += age_pts
        reasons.append(f"Open for {int(age_days)} days (+{age_pts})")
    rec_pts = min(recurrence_count * c["recurrence_per_repeat"], c["recurrence_max"])
    if rec_pts:
        total += rec_pts
        reasons.append(f"Recurred {recurrence_count} time(s) (+{rec_pts})")

    total = min(total, 100)
    thresholds = sorted(c["priority_thresholds"].items(), key=lambda kv: -kv[1])
    priority = next(p for p, minimum in thresholds if total >= minimum)
    return Score(total=total, priority=priority, reasons=reasons)


def add_business_days(start: datetime, days: int) -> datetime:
    d = start
    while days > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days -= 1
    return d


def due_date(priority: str, start: datetime) -> datetime:
    days = config.load("scoring.yaml")["sla_business_days"][priority]
    if priority == "P4":
        return start + timedelta(days=_BUSINESS_DAYS_FALLBACK_CALENDAR)
    end = add_business_days(start, days)
    return end.replace(hour=23, minute=59, second=0, microsecond=0)
