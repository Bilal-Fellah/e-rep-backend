# Lightweight in-memory rate limiting (fixed window), used to throttle failed
# logins. No external dependency, no Redis — same spirit as api_key_auth.py.
#
# NOTE: the counters are per-process, so with multiple gunicorn workers the
# effective limit is (workers x limit). This blunts password brute-forcing but
# is not a hard global cap; use a shared store (Redis / Flask-Limiter) if you
# need one, and note it does not stop a distributed/botnet attack spread across
# many IPs against a single account.
import os
import time
from threading import Lock

_store: dict[str, dict] = {}
_lock = Lock()

# Hard cap on tracked keys so a flood of distinct keys can't exhaust memory.
_MAX_KEYS = 10000

# Number of trusted reverse proxies in front of the app. Each trusted proxy
# appends the address it saw to X-Forwarded-For, so the real client is the entry
# this many positions from the right — NOT the left-most, which is
# attacker-controllable. Default 1 (a single nginx in front). Set to 0 when the
# app is exposed directly (use the socket address).
TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))


def _prune(now: float) -> None:
    """Keep the store hard-bounded: drop expired entries, and if still over the
    cap, evict the soonest-to-expire so distinct-key floods can't grow it."""
    if len(_store) <= _MAX_KEYS:
        return
    for key in [k for k, v in _store.items() if now >= v["reset"]]:
        del _store[key]
    if len(_store) > _MAX_KEYS:
        overflow = len(_store) - _MAX_KEYS
        for key in sorted(_store, key=lambda k: _store[k]["reset"])[:overflow]:
            del _store[key]


def too_many_failures(key: str, max_failures: int):
    """Return (limited, retry_after_seconds). Read-only — checking does not
    itself count as an attempt, so this is safe to call before validating
    credentials. `limited` is True once `key` has recorded >= max_failures in
    the current window."""
    now = time.time()
    with _lock:
        _prune(now)
        entry = _store.get(key)
        if entry is None or now >= entry["reset"]:
            return False, 0
        if entry["count"] >= max_failures:
            return True, max(1, int(entry["reset"] - now))
        return False, 0


def record_failure(key: str, window_seconds: int) -> None:
    """Record one failed attempt for `key`, opening a new window if needed."""
    now = time.time()
    with _lock:
        _prune(now)
        entry = _store.get(key)
        if entry is None or now >= entry["reset"]:
            _store[key] = {"count": 1, "reset": now + window_seconds}
        else:
            entry["count"] += 1


def client_ip() -> str:
    """Client IP for rate-limit keying, resolved through TRUSTED_PROXY_COUNT
    trusted proxies. Because each trusted proxy appends the address it saw, the
    real client is the Nth-from-right X-Forwarded-For entry; the left-most is
    attacker-supplied and must not be trusted for a security control. Falls back
    to the socket address."""
    from flask import request

    if TRUSTED_PROXY_COUNT > 0:
        forwarded = request.headers.get("X-Forwarded-For", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= TRUSTED_PROXY_COUNT:
            return parts[-TRUSTED_PROXY_COUNT]
    return request.remote_addr or "unknown"
