# Read-access to the JSONL error logs written by api/utils/logging_utils.py.
#
# Those logs are rotated monthly into files named "<prefix>-<YYYY-MM>.jsonl"
# (one JSON object per line). This repository locates and tails them so the
# admin dashboard can display and the alerts endpoint can count errors. It is
# read-only — it never writes to the log files.
import json
import os
from datetime import datetime, timezone

from flask import current_app

# Cap how many of the most recent lines we parse per source/month. The rotating
# handler allows files up to 100MB; parsing every line on each admin request
# (the alerts view polls on an interval) is wasteful, so we tail the file and
# only JSON-parse the most recent window. Viewing/paginating is scoped to this
# window of newest entries.
MAX_SCAN_LINES = 20000


# Each log source: the request-context prefix + the config keys logging_utils
# uses to resolve its directory (falling back to <app.root_path>/../logs).
SOURCES = {
    "route": {
        "prefix_key": "ROUTE_ERROR_FILE_PREFIX",
        "prefix_default": "route-errors",
        "dir_keys": ["ROUTE_ERROR_LOG_DIR", "ERROR_LOG_DIR"],
    },
    "service": {
        "prefix_key": "SERVICE_ERROR_FILE_PREFIX",
        "prefix_default": "service-errors",
        "dir_keys": ["SERVICE_ERROR_LOG_DIR", "ERROR_LOG_DIR"],
    },
    "repository": {
        "prefix_key": "REPOSITORY_ERROR_FILE_PREFIX",
        "prefix_default": "repository-errors",
        "dir_keys": ["REPOSITORY_ERROR_LOG_DIR", "ERROR_LOG_DIR"],
    },
}

VALID_SEVERITIES = ("low", "medium", "high")


class LogRepository:
    @staticmethod
    def _default_dir() -> str:
        return os.path.abspath(os.path.join(current_app.root_path, "..", "logs"))

    @staticmethod
    def _resolve(source: str):
        cfg = SOURCES[source]
        prefix = current_app.config.get(cfg["prefix_key"], cfg["prefix_default"])
        log_dir = None
        for key in cfg["dir_keys"]:
            value = current_app.config.get(key)
            if value:
                log_dir = value
                break
        if not log_dir:
            log_dir = LogRepository._default_dir()
        return prefix, log_dir

    @staticmethod
    def _current_period() -> str:
        now = datetime.now(timezone.utc)
        return f"{now.year:04d}-{now.month:02d}"

    @staticmethod
    def _sources_for(source: str | None):
        if not source or source == "all":
            return list(SOURCES.keys())
        return [source] if source in SOURCES else []

    @staticmethod
    def available_periods(source: str | None = None) -> list[str]:
        """Distinct YYYY-MM periods that have log files, newest first."""
        periods: set[str] = set()
        for src in LogRepository._sources_for(source):
            prefix, log_dir = LogRepository._resolve(src)
            if not os.path.isdir(log_dir):
                continue
            for name in os.listdir(log_dir):
                if name.startswith(f"{prefix}-") and name.endswith(".jsonl"):
                    period = name[len(prefix) + 1 : -len(".jsonl")]
                    # Guard against rotation-suffixed backups (…-YYYY-MM.jsonl.1)
                    if len(period) == 7 and period[4] == "-":
                        periods.add(period)
        return sorted(periods, reverse=True)

    @staticmethod
    def _tail_lines(path: str, max_lines: int) -> list[str]:
        """Return the last `max_lines` lines of a file, reading from the end in
        blocks so a large (up to 100MB) log file is not streamed in full."""
        block_size = 65536
        blocks: list[bytes] = []
        newlines = 0
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            remaining = fh.tell()
            # Read until we've seen more newlines than we need, or hit the start.
            while remaining > 0 and newlines <= max_lines:
                read_size = min(block_size, remaining)
                remaining -= read_size
                fh.seek(remaining)
                chunk = fh.read(read_size)
                blocks.append(chunk)
                newlines += chunk.count(b"\n")
        data = b"".join(reversed(blocks))
        # The earliest block may start mid-line; splitlines()[-max_lines:] drops
        # that partial leading line along with anything beyond the window.
        lines = data.decode("utf-8", errors="replace").splitlines()
        return lines[-max_lines:]

    @staticmethod
    def _read_file(source: str, period: str) -> list[dict]:
        prefix, log_dir = LogRepository._resolve(source)
        path = os.path.join(log_dir, f"{prefix}-{period}.jsonl")
        if not os.path.isfile(path):
            return []
        entries: list[dict] = []
        # Tail a bounded window instead of reading/parsing the whole file.
        for line in LogRepository._tail_lines(path, MAX_SCAN_LINES):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(obj, dict):
                obj["_source"] = source
                entries.append(obj)
        return entries

    @staticmethod
    def read_logs(
        source: str | None = None,
        severity: str | None = None,
        period: str | None = None,
        limit: int = 100,
        offset: int = 0,
        include_periods: bool = True,
    ) -> dict:
        period = period or LogRepository._current_period()

        combined: list[dict] = []
        for src in LogRepository._sources_for(source):
            combined.extend(LogRepository._read_file(src, period))

        if severity in VALID_SEVERITIES:
            combined = [e for e in combined if e.get("severity") == severity]

        # Newest first. ISO-8601 timestamps sort correctly as strings.
        combined.sort(key=lambda e: e.get("timestamp") or "", reverse=True)

        total = len(combined)
        page = combined[offset : offset + limit]
        return {
            "logs": page,
            "total": total,
            "period": period,
            "source": source or "all",
            # The period list is only for the logs UI dropdown; callers that
            # don't need it (e.g. the alerts aggregation) skip the dir scan.
            "available_periods": (
                LogRepository.available_periods(source) if include_periods else []
            ),
        }

    @staticmethod
    def recent_high_severity(limit: int = 10) -> tuple[int, list[dict]]:
        """(count, sample) of high-severity entries in the current month across
        all sources — feeds the alerts 'system errors' category."""
        result = LogRepository.read_logs(
            source="all",
            severity="high",
            limit=limit,
            offset=0,
            include_periods=False,
        )
        return result["total"], result["logs"]
