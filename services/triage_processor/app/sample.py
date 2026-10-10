"""Load sample SCC findings (sample_data/findings.json) for demos and local runs."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .parser import parse_notification

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data" / "findings.json"


def payloads(path: Path = SAMPLE, now: datetime | None = None) -> list[dict]:
    """SCC notification payloads, oldest first, with event times relative to now."""
    now = now or datetime.now(timezone.utc)
    items = json.loads(Path(path).read_text())
    out = []
    for it in sorted(items, key=lambda i: -i["days_ago"]):
        p = copy.deepcopy(it["payload"])
        p["finding"]["eventTime"] = (now - timedelta(days=it["days_ago"])).isoformat().replace("+00:00", "Z")
        out.append(p)
    return out


def load_into(processor, **kw) -> list:
    return [processor.process(parse_notification(p)) for p in payloads(**kw)]
