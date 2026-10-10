"""Parse SCC notification payloads (Pub/Sub message data)."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone

from .models import Finding


class ParseError(ValueError):
    pass


_FRAC = re.compile(r"\.(\d+)")


def _ts(value: str | None) -> datetime:
    if not value:
        raise ParseError("finding has no eventTime/createTime")
    # SCC emits nanosecond fractions; fromisoformat accepts at most microseconds.
    v = _FRAC.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), value.replace("Z", "+00:00"), count=1)
    try:
        dt = datetime.fromisoformat(v)
    except ValueError as e:
        raise ParseError(f"bad timestamp {value!r}") from e
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def decode_pubsub_message(envelope: dict) -> dict:
    """Extract the JSON body from a Pub/Sub push envelope."""
    try:
        data = envelope["message"]["data"]
        return json.loads(base64.b64decode(data))
    except (KeyError, ValueError, TypeError) as e:
        raise ParseError(f"bad Pub/Sub envelope: {e}") from e


def parse_notification(payload: dict) -> Finding:
    f = payload.get("finding")
    if not f:
        raise ParseError("payload has no 'finding'")
    name = f.get("name", "")
    parts = name.split("/")
    # organizations/{org}/sources/{source}/findings/{finding}
    if "sources" not in parts or "findings" not in parts:
        raise ParseError(f"unexpected finding name: {name!r}")
    source_id = parts[parts.index("sources") + 1]
    finding_id = parts[parts.index("findings") + 1]

    resource = payload.get("resource", {}) or {}
    project_id = (
        resource.get("projectDisplayName")
        or (resource.get("projectName") or "").split("/")[-1]
        or ""
    )
    for required in ("category", "resourceName"):
        if not f.get(required):
            raise ParseError(f"finding missing {required}")

    return Finding(
        finding_name=name,
        source_id=source_id,
        finding_id=finding_id,
        category=f["category"],
        severity=f.get("severity") or "SEVERITY_UNSPECIFIED",
        scc_state=f.get("state") or "ACTIVE",
        resource_name=f["resourceName"],
        project_id=project_id,
        event_time=_ts(f.get("eventTime") or f.get("createTime")),
        resource_type=resource.get("type", ""),
        labels=resource.get("labels") or resource.get("resourceLabels") or {},
        raw=payload,
    )
