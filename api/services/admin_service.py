# Business workflows for the admin dashboard: log reading + alert aggregation.
from datetime import datetime, timedelta, timezone

from api.repositories.entity_repository import EntityRepository
from api.repositories.log_repository import LogRepository
from api.repositories.page_repository import PageRepository
from api.repositories.scraping_session_repository import ScrapingSessionRepository
from api.repositories.user_repository import UserRepository
from api.utils.logging_utils import instrument_service_class

# How far back "recent" looks for scraping-failure alerts.
FAILURE_WINDOW_DAYS = 7


@instrument_service_class
class AdminService:
    @staticmethod
    def get_logs(source=None, severity=None, period=None, limit=100, offset=0):
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        return LogRepository.read_logs(
            source=source,
            severity=severity,
            period=period,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def get_overview():
        """Cheap aggregate counts for the dashboard landing — computed in the DB
        so the client doesn't download full entity/page tables just to count."""
        entities_by_type = EntityRepository.count_by_type()
        pages_by_platform = PageRepository.count_by_platform()
        return {
            "entities": {
                "total": sum(entities_by_type.values()),
                "active": EntityRepository.count_active(),
                "by_type": entities_by_type,
            },
            "pages": {
                # platform is NOT NULL, so the grouped counts already sum to the
                # total — no separate COUNT query needed.
                "total": sum(pages_by_platform.values()),
                "by_platform": pages_by_platform,
            },
            "users": {
                "total": UserRepository.count_users(),
                "unverified": UserRepository.count_unverified(),
            },
        }

    @staticmethod
    def get_alerts():
        """Aggregate the four alert categories on the fly from existing data.

        Severity scale: "critical" | "serious" | "warning" | "ok". The frontend
        pairs each with an icon + label (never color alone)."""
        now = datetime.now(timezone.utc)
        # ScrapingSession.created_at is stored naive (datetime.utcnow), so the
        # window bound must also be naive UTC — otherwise Postgres compares a
        # naive column against a tz-aware value and the boundary drifts by the
        # session timezone offset.
        since = datetime.utcnow() - timedelta(days=FAILURE_WINDOW_DAYS)

        # 1) Scraping failures (last 7 days)
        failed = ScrapingSessionRepository.get_recent_failed(since, limit=10)
        failures_category = {
            "key": "scraping_failures",
            "label": "Scraping failures",
            "count": len(failed),
            "severity": "serious" if failed else "ok",
            "items": [
                {
                    "session_id": s.session_id,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "error": s.error_message,
                }
                for s in failed
            ],
        }

        # 2) Accounts awaiting activation (is_verified = False)
        unverified_count = UserRepository.count_unverified()
        unverified = UserRepository.list_unverified(limit=10)
        activation_category = {
            "key": "accounts_to_activate",
            "label": "Accounts to activate",
            "count": unverified_count,
            "severity": "warning" if unverified_count else "ok",
            "items": [
                {
                    "user_id": u.id,
                    "email": u.email,
                    "name": f"{u.first_name} {u.last_name}".strip(),
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in unverified
            ],
        }

        # 3) Data anomalies — entities flagged to_scrape but with no pages
        broken_count = EntityRepository.count_active_without_pages()
        broken = EntityRepository.get_active_without_pages(limit=10)
        anomalies_category = {
            "key": "data_anomalies",
            "label": "Data anomalies",
            "count": broken_count,
            "severity": "warning" if broken_count else "ok",
            "items": [
                {
                    "entity_id": e.id,
                    "name": e.name,
                    "type": e.type,
                    "reason": "Active for scraping but has no pages",
                }
                for e in broken
            ],
        }

        # 4) System / API errors — high-severity log entries this month
        error_count, error_items = LogRepository.recent_high_severity(limit=10)
        system_category = {
            "key": "system_errors",
            "label": "System errors",
            "count": error_count,
            "severity": "critical" if error_count else "ok",
            "items": [
                {
                    "timestamp": e.get("timestamp"),
                    "source": e.get("_source"),
                    "error_type": e.get("error_type"),
                    "message": e.get("public_message") or e.get("error_message"),
                    "status_code": e.get("status_code"),
                }
                for e in error_items
            ],
        }

        categories = [
            failures_category,
            activation_category,
            anomalies_category,
            system_category,
        ]
        total = sum(c["count"] for c in categories)

        return {
            "generated_at": now.isoformat(),
            "total": total,
            "summary": {c["key"]: c["count"] for c in categories},
            "categories": categories,
        }
