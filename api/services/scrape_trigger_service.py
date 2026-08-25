# Service layer for manually triggering own-scraper runs (profile/comments)
# from the admin API, and letting the VPS-side watcher claim + report on
# them. See api/models/scrape_trigger_request_model.py for why this queue
# exists instead of the backend reaching into the VPS directly.
from datetime import datetime, timezone

from api.repositories.scrape_trigger_repository import ScrapeTriggerRepository
from api.utils.logging_utils import instrument_service_class

# Only (platform, mode) pairs with a real, working scraper on the VPS today
# -- each maps 1:1 to a systemd service the watcher runs via `systemctl
# start` (see trigger_watcher.py's SERVICE_MAP, kept in sync with this by
# hand -- there is no shared source of truth across the repo boundary).
#
# Deliberately excludes:
#   - Bright Data / Apify: external, quota/cost-metered -- not something to
#     expose as a click-anytime admin button (Apify especially: manual-only
#     by standing instruction).
#   - Any (platform, mode) with no real capability yet, e.g. facebook
#     "profile" -- auth is wired but there is no extraction logic behind it.
TRIGGERABLE = frozenset(
    {
        ("instagram", "profile"),
        ("instagram", "comments"),
        ("linkedin", "comments"),
        ("tiktok", "comments"),
        ("facebook", "comments"),
        ("youtube", "comments"),
        # Client-tracked-keyword mentions (api/services/tracked_keyword_service.py),
        # not comments -- the "Run now" action on Erup's Keywords page for
        # admins (api/routes/data/keywords.py), separate from Brendex
        # Admin's generic trigger panel.
        ("tiktok", "keyword-search"),
    }
)

REPORTABLE_STATUSES = ("done", "failed")


class ScrapeTriggerError(ValueError):
    """Raised for an invalid platform/mode/status on this surface."""


@instrument_service_class
class ScrapeTriggerService:
    @staticmethod
    def _validate_platform_mode(platform: str, mode: str) -> None:
        if (platform, mode) not in TRIGGERABLE:
            options = ", ".join(f"{p}/{m}" for p, m in sorted(TRIGGERABLE))
            raise ScrapeTriggerError(f"'{platform}'/'{mode}' isn't triggerable (only {options} today).")

    @staticmethod
    def request_trigger(platform: str, mode: str, requested_by: int | None = None) -> dict:
        ScrapeTriggerService._validate_platform_mode(platform, mode)
        row = ScrapeTriggerRepository.create(platform=platform, mode=mode, requested_by=requested_by)
        return ScrapeTriggerService._serialize(row)

    @staticmethod
    def list_recent(limit: int = 50) -> list[dict]:
        return [ScrapeTriggerService._serialize(r) for r in ScrapeTriggerRepository.list_recent(limit)]

    @staticmethod
    def latest_for(platform: str, mode: str) -> dict | None:
        row = ScrapeTriggerRepository.latest_for(platform, mode)
        return ScrapeTriggerService._serialize(row) if row is not None else None

    @staticmethod
    def claim_next_pending() -> dict | None:
        """VPS-facing: atomically claim the oldest pending request, if any."""
        row = ScrapeTriggerRepository.claim_next_pending(started_at=datetime.now(timezone.utc))
        return ScrapeTriggerService._serialize(row) if row is not None else None

    @staticmethod
    def report_result(request_id: int, status: str, detail: str | None = None) -> dict:
        """VPS-facing: record the outcome of a claimed run."""
        if status not in REPORTABLE_STATUSES:
            raise ScrapeTriggerError(f"status must be one of {REPORTABLE_STATUSES}.")
        row = ScrapeTriggerRepository.report_result(
            request_id=request_id,
            status=status,
            detail=detail,
            finished_at=datetime.now(timezone.utc),
        )
        if row is None:
            raise ScrapeTriggerError(f"No trigger request with id {request_id}.")
        return ScrapeTriggerService._serialize(row)

    @staticmethod
    def _serialize(row) -> dict:
        return {
            "id": row.id,
            "platform": row.platform,
            "mode": row.mode,
            "status": row.status,
            "requested_by": row.requested_by,
            "requested_at": row.requested_at.isoformat() if row.requested_at else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "detail": row.detail,
        }
