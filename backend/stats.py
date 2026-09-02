"""Lightweight, file-backed usage counters: page visits, and recommendation
generations tracked separately for snack box vs hamper. This project has no
database (see data_provider.py's cache-file pattern) - same convention here,
an in-memory-on-read dict flushed to a JSON file on every change, guarded by
a lock for concurrent-request safety.

Deliberately NOT exposed anywhere in the frontend UI or nav - only reachable
via GET /api/stats in app.py, gated behind a shared-secret header
(STATS_ACCESS_KEY env var) so it's visible only to whoever holds that key,
not to every BD user of the deployed tool. See app.py's endpoint for the
404-not-403 reasoning (don't reveal the endpoint exists to a wrong guess).

Caveat this module can't avoid (same one that applies to the product
catalog cache): a bare Render deploy has no persistent disk, so this file
resets to zero on every redeploy - it is a live-session counter, not a
durable log. Flagged explicitly to the user, not silently accepted.
"""

import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS_PATH = Path(os.environ.get("USAGE_STATS_PATH", str(ROOT / ".cache" / "usage_stats.json")))

_LOCK = threading.Lock()
_DEFAULT_STATS = {
    "visits": 0,
    "snack_box_recommendations": 0,
    "hamper_recommendations": 0,
}


def _load() -> dict:
    if STATS_PATH.exists():
        try:
            data = json.loads(STATS_PATH.read_text())
            if isinstance(data, dict):
                return {**_DEFAULT_STATS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULT_STATS)


def _save(data: dict) -> None:
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(data))


def _increment(key: str) -> None:
    with _LOCK:
        data = _load()
        data[key] = data.get(key, 0) + 1
        _save(data)


def record_visit() -> None:
    _increment("visits")


def record_snack_box_recommendation() -> None:
    _increment("snack_box_recommendations")


def record_hamper_recommendation() -> None:
    _increment("hamper_recommendations")


def get_stats() -> dict:
    with _LOCK:
        return _load()
