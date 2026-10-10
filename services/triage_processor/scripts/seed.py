"""Post the sample findings to a running processor as Pub/Sub push messages.

    python scripts/seed.py [http://localhost:8080]
"""
import base64
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.sample import payloads  # noqa: E402

base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
for p in payloads():
    body = {"message": {"data": base64.b64encode(json.dumps(p).encode()).decode()}}
    req = urllib.request.Request(f"{base}/pubsub/push", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req))
    print(f"{p['finding']['category']:<22} {r['action']:<22} {r['finding_uid']}")
