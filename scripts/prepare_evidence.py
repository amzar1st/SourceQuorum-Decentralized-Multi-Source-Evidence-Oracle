#!/usr/bin/env python3
"""Fetch a pinned Wayback body and print submit_evidence arguments. Never creates an archive."""
import argparse
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone

MAX_BODY = 80000


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("claim_id")
    p.add_argument("source_index", type=int, choices=range(3))
    p.add_argument("original_url")
    p.add_argument("archive_url")
    a = p.parse_args()
    match = re.fullmatch(r"https://web\.archive\.org/web/([0-9]{14})id_/(https://\S+)", a.archive_url)
    if not match or match[2] != a.original_url:
        p.error("Archive must contain an exact capture timestamp, id_ mode, and the original HTTPS URL")
    requested = datetime.strptime(match[1], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    try:
        request = urllib.request.Request(a.archive_url, headers={"User-Agent": "SourceQuorum/1.0 evidence-preparer"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(MAX_BODY + 1)
            capture = datetime.strptime(response.headers.get("Memento-Datetime", ""), "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
            mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if response.status != 200 or not 0 < len(body) <= MAX_BODY:
                raise ValueError("Archive unavailable or body outside 1..80000 bytes")
            if capture != requested:
                raise ValueError("Archive redirected to another capture; use its exact timestamp explicitly")
            if mime not in ("text/html", "text/plain", "application/xhtml+xml", "application/json"):
                raise ValueError("Unsupported content type")
            body.decode("utf-8")
    except Exception as exc:
        p.exit(1, f"Evidence preparation failed: {exc}\n")
    print(json.dumps({"method": "submit_evidence", "args": [a.claim_id, a.source_index, a.original_url,
                     a.archive_url, hashlib.sha256(body).hexdigest()],
                     "capture_utc": capture.isoformat(), "body_bytes": len(body)}, indent=2))


if __name__ == "__main__":
    main()
