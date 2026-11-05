"""Race data from OpenF1 (no login): laps, tyre stints, pit stops and race control messages, 2023 onward.

Calls are spaced out and retried. Finished sessions are cached on disk, one file per call,
so an interrupted run resumes where it stopped.
"""
import hashlib
import json
import time

import requests

from ..config import CACHE

BASE = "https://api.openf1.org/v1"
_last = 0.0


def get(endpoint, **params):
    global _last
    key = hashlib.md5(f"{endpoint}{sorted(params.items())}".encode()).hexdigest()
    file = CACHE / "openf1" / f"lab_{endpoint}_{key}.json"
    if file.exists():
        return json.loads(file.read_text())
    for attempt in range(8):
        wait = 0.5 - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=60)
        except (requests.Timeout, requests.ConnectionError):
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 404:  # OpenF1 answers 404 when a query has no rows
            data = []
        else:
            r.raise_for_status()
            data = r.json()
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data))
        return data
    raise RuntimeError(f"OpenF1 kept failing for {endpoint} {params}")
