# Business workflows for the admin dashboard: log reading + alert aggregation.
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from api import db
from api.repositories.entity_repository import EntityRepository
from api.repositories.log_repository import LogRepository
from api.repositories.page_repository import PageRepository
from api.repositories.scraping_session_repository import ScrapingSessionRepository
from api.repositories.user_repository import UserRepository
from api.utils.datetime_utils import iso_utc
from api.utils.logging_utils import instrument_service_class

# How far back "recent" looks for scraping-failure alerts.
FAILURE_WINDOW_DAYS = 7
# A scrape is "stale" if the last successful session is older than this.
SCRAPE_STALE_HOURS = 26


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
    def get_health():
        """System health snapshot: DB reachability, scrape freshness, and the
        recent high-severity error count. Read-only and best-effort."""
        try:
            db.session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db.session.rollback()
            db_ok = False

        # The log-error count doesn't touch the DB, so report it either way.
        # A health check must degrade to null, never 500 on a sub-check failure.
        try:
            error_count, _ = LogRepository.recent_high_severity(limit=1)
        except Exception:
            error_count = None

        # If the DB is down, skip the session queries — they'd raise against the
        # same dead connection and turn this health check into a 500.
        scraping = {
            "last_session_at": None,
            "last_session_status": None,
            "last_success_at": None,
            "stale": True,
        }
        if db_ok:
            try:
                latest = ScrapingSessionRepository.get_latest()
                latest_completed = ScrapingSessionRepository.get_latest_completed()
                last_success = (
                    latest_completed.completed_at if latest_completed else None
                )
                # completed_at is stored naive UTC — compare against naive UTC.
                threshold = datetime.utcnow() - timedelta(hours=SCRAPE_STALE_HOURS)
                scraping = {
                    "last_session_at": iso_utc(latest.created_at) if latest else None,
                    "last_session_status": latest.status if latest else None,
                    "last_success_at": iso_utc(last_success),
                    "stale": last_success is None or last_success < threshold,
                }
            except Exception:
                db.session.rollback()  # leave scraping at its unknown defaults

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "db_ok": db_ok,
            "scraping": scraping,
            "errors": {"high_severity": error_count},
        }

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
                    "created_at": iso_utc(s.created_at),
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
                    "created_at": iso_utc(u.created_at),
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
