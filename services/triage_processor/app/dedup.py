import hashlib

from .models import Finding


def dedup_key(f: Finding) -> str:
    """Stable key for 'the same issue on the same resource'."""
    raw = "|".join([f.source_id, f.category, f.resource_name])
    return hashlib.sha256(raw.encode()).hexdigest()


def event_id(f: Finding) -> str:
    """Idempotency key: one id per (finding, event time)."""
    raw = f"{f.finding_name}|{f.event_time.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def finding_uid(key: str, recurrence: int = 0) -> str:
    return f"f-{key[:8]}" + (f"-r{recurrence}" if recurrence else "")
