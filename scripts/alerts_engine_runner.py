#!/usr/bin/env python3
"""
External alerts runner (to be deployed on a timer host).

Flow:
1) GET /api/alerts/engine/readiness
2) If ready, POST /api/alerts/engine/run

Environment variables:
- BACKEND_URL (required), e.g. https://api.example.com
- ALERTS_ENGINE_API_KEY (required)
- RUN_DRY (optional: true/false, default false)
- ALERTS_DETECTORS (optional CSV), e.g. negative_comment,keyword_comment
- HTTP_TIMEOUT_SECONDS (optional int, default 25)
"""

from __future__ import annotations

import json
import os
import sys
import requests


def _bool_env(name: str, default: bool = False) -> bool:
    value = (os.getenv(name) or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> list[str] | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def _required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    backend_url = _required("BACKEND_URL").rstrip("/")
    api_key = _required("ALERTS_ENGINE_API_KEY")

    timeout = int((os.getenv("HTTP_TIMEOUT_SECONDS") or "25").strip() or "25")
    run_dry = _bool_env("RUN_DRY", default=False)
    detectors = _csv_env("ALERTS_DETECTORS")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    readiness_url = f"{backend_url}/api/alerts/engine/readiness"
    run_url = f"{backend_url}/api/alerts/engine/run"

    readiness_resp = requests.get(readiness_url, headers=headers, timeout=timeout)
    readiness_resp.raise_for_status()
    readiness_payload = readiness_resp.json()

    if not readiness_payload.get("success"):
        print(json.dumps({"stage": "readiness", "ok": False, "payload": readiness_payload}, ensure_ascii=False))
        return 1

    readiness = readiness_payload.get("data") or {}
    if not readiness.get("ready"):
        print(json.dumps({"stage": "readiness", "ok": True, "ready": False, "reason": readiness.get("reason"), "context": readiness.get("context")}, ensure_ascii=False))
        return 0

    body = {"dry_run": run_dry}
    if detectors:
        body["detectors"] = detectors

    run_resp = requests.post(run_url, headers=headers, json=body, timeout=timeout)
    run_resp.raise_for_status()
    run_payload = run_resp.json()

    if not run_payload.get("success"):
        print(json.dumps({"stage": "run", "ok": False, "payload": run_payload}, ensure_ascii=False))
        return 1

    print(json.dumps({"stage": "run", "ok": True, "result": run_payload.get("data")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        status = response.status_code if response is not None else None
        body = response.text if response is not None else str(exc)
        print(json.dumps({"ok": False, "error": "http_error", "status": status, "body": body}, ensure_ascii=False))
        raise SystemExit(1)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
