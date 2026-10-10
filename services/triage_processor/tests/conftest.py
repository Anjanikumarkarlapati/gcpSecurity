import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ["CONFIG_DIR"] = str(ROOT / "config")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.notifier import RecordingNotifier
from app.processor import Processor
from app.store import InMemoryStore


def make_payload(category="PUBLIC_BUCKET_ACL", severity="HIGH", state="ACTIVE",
                 project="t051-production", resource="//storage.googleapis.com/buckets/b1",
                 event_time="2026-10-05T10:00:00.123456789Z", finding="f1", labels=None):
    return {
        "finding": {
            "name": f"organizations/1/sources/2/findings/{finding}",
            "category": category, "severity": severity, "state": state,
            "resourceName": resource, "eventTime": event_time,
        },
        "resource": {"projectDisplayName": project, "type": "google.cloud.storage.Bucket",
                     "labels": {"data-classification": "sensitive"} if labels is None else labels},
    }


def envelope(payload):
    return {"message": {"data": base64.b64encode(json.dumps(payload).encode()).decode()}}


@pytest.fixture
def notifier():
    return RecordingNotifier()


@pytest.fixture
def processor(notifier):
    return Processor(InMemoryStore(), notifier)
