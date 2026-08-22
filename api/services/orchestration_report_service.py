# Read-only reporting over the scrape_attempts audit log — the "is our
# paid data actually available today, and what's the success rate when it
# isn't" view the orchestration task calls for. Mirrors the shape of
# DataIntegrityService/ScrapingService's daily-summary methods so the admin
# dashboard can render this the same way it already renders those.
from datetime import datetime, timedelta, timezone

from api.repositories.scrape_attempt_repository import ScrapeAttemptRepository
from api.utils.datetime_utils import iso_utc
from api.utils.logging_utils import instrument_service_class


def _rate(n, total):
    return round(n / total, 4) if total else None


@instrument_service_class
class OrchestrationReportService:
    @staticmethod
    def get_summary(days: int = 7, platform: str = None, domain: str = None) -> dict:
        since = datetime.now() - timedelta(days=max(1, min(int(days), 90)))
        rows = ScrapeAttemptRepository.get_summary_since(since, platform=platform, domain=domain)

        by_platform = []
        totals = {"total": 0, "complete": 0, "partial": 0, "failed": 0, "fallback_invoked": 0, "total_cost_usd": 0.0}
        for row in rows:
            total = int(row.total)
            entry = {
                "platform": row.platform,
                "domain": row.domain,
                "total": total,
                "complete": int(row.complete or 0),
                "partial": int(row.partial or 0),
                "failed": int(row.failed or 0),
                "success_rate": _rate(int(row.complete or 0), total),
                "degraded_rate": _rate(int(row.partial or 0) + int(row.failed or 0), total),
                "fallback_invoked": int(row.fallback_invoked or 0),
                "fallback_rate": _rate(int(row.fallback_invoked or 0), total),
                "total_cost_usd": float(row.total_cost_usd or 0),
            }
            by_platform.append(entry)
            for key in ("total", "complete", "partial", "failed", "fallback_invoked"):
                totals[key] += entry[key]
            totals["total_cost_usd"] += entry["total_cost_usd"]

        totals["success_rate"] = _rate(totals["complete"], totals["total"])
        totals["degraded_rate"] = _rate(totals["partial"] + totals["failed"], totals["total"])

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "days": days,
            "platform_filter": platform,
            "domain_filter": domain,
            "totals": totals,
            "by_platform": by_platform,
        }

    @staticmethod
    def get_daily(days: int = 14, platform: str = None, domain: str = None) -> list:
        rows = ScrapeAttemptRepository.get_daily(days=days, platform=platform, domain=domain)
        return [
            {
                "date": str(row.day),
                "platform": row.platform,
                "domain": row.domain,
                "total": int(row.total),
                "complete": int(row.complete or 0),
                "partial": int(row.partial or 0),
                "failed": int(row.failed or 0),
                "total_cost_usd": float(row.total_cost_usd or 0),
            }
            for row in rows
        ]

    @staticmethod
    def list_recent_attempts(platform: str = None, domain: str = None, final_status: str = None, limit: int = 50) -> list:
        rows = ScrapeAttemptRepository.list_recent(
            platform=platform, domain=domain, final_status=final_status, limit=limit
        )
        return [
            {
                "id": row.id,
                "page_id": str(row.page_id),
                "platform": row.platform,
                "domain": row.domain,
                "started_at": iso_utc(row.started_at),
                "primary_source": row.primary_source,
                "primary_status": row.primary_status,
                "primary_missing_fields": row.primary_missing_fields,
                "fallback_chain": row.fallback_chain,
                "final_status": row.final_status,
                "final_missing_fields": row.final_missing_fields,
                "total_cost_usd": float(row.total_cost_usd or 0),
                "pages_history_id": row.pages_history_id,
                "error_message": row.error_message,
            }
            for row in rows
        ]
