# Data-access methods for the scrape attempts audit log (see
# api/models/scrape_attempt_model.py for what each row represents).
from datetime import datetime, timedelta

from api import db
from api.models.scrape_attempt_model import ScrapeAttempt
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class ScrapeAttemptRepository:
    @staticmethod
    def create(
        page_id,
        platform: str,
        domain: str,
        primary_source: str,
        primary_status: str,
        primary_missing_fields: list,
        fallback_chain: list,
        final_status: str,
        final_missing_fields: list,
        total_cost_usd: float,
        pages_history_id: int = None,
        error_message: str = None,
        commit: bool = True,
    ) -> ScrapeAttempt:
        row = ScrapeAttempt(
            page_id=page_id,
            platform=platform,
            domain=domain,
            primary_source=primary_source,
            primary_status=primary_status,
            primary_missing_fields=primary_missing_fields or [],
            fallback_chain=fallback_chain or [],
            final_status=final_status,
            final_missing_fields=final_missing_fields or [],
            total_cost_usd=total_cost_usd or 0,
            pages_history_id=pages_history_id,
            error_message=error_message,
        )
        db.session.add(row)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return row

    @staticmethod
    def get_by_id(attempt_id: int) -> ScrapeAttempt | None:
        return ScrapeAttempt.query.get(attempt_id)

    @staticmethod
    def list_recent(platform: str = None, domain: str = None, final_status: str = None, limit: int = 50) -> list[ScrapeAttempt]:
        query = ScrapeAttempt.query
        if platform:
            query = query.filter_by(platform=platform)
        if domain:
            query = query.filter_by(domain=domain)
        if final_status:
            query = query.filter_by(final_status=final_status)
        return query.order_by(ScrapeAttempt.started_at.desc()).limit(limit).all()

    @staticmethod
    def get_summary_since(since: datetime, platform: str = None, domain: str = None) -> list:
        """Per platform+domain: how many attempts landed complete/partial/
        failed, and how much the fallback chain cost, since `since`. Built
        with portable SQLAlchemy case()/count() (see
        PageHistoryRepository's data-integrity queries for the same
        convention) so it runs identically on Postgres and the sqlite test
        DB."""
        from sqlalchemy import case

        query = db.session.query(
            ScrapeAttempt.platform,
            ScrapeAttempt.domain,
            db.func.count().label("total"),
            db.func.sum(case((ScrapeAttempt.final_status == "complete", 1), else_=0)).label("complete"),
            db.func.sum(case((ScrapeAttempt.final_status == "partial", 1), else_=0)).label("partial"),
            db.func.sum(case((ScrapeAttempt.final_status == "failed", 1), else_=0)).label("failed"),
            db.func.sum(
                case((ScrapeAttempt.primary_status != "complete", 1), else_=0)
            ).label("fallback_invoked"),
            db.func.sum(ScrapeAttempt.total_cost_usd).label("total_cost_usd"),
        ).filter(ScrapeAttempt.started_at >= since)

        if platform:
            query = query.filter(ScrapeAttempt.platform == platform)
        if domain:
            query = query.filter(ScrapeAttempt.domain == domain)

        return query.group_by(ScrapeAttempt.platform, ScrapeAttempt.domain).all()

    @staticmethod
    def get_daily(days: int = 14, platform: str = None, domain: str = None) -> list:
        from sqlalchemy import case

        since = datetime.now() - timedelta(days=days)
        day = db.func.date(ScrapeAttempt.started_at)

        query = db.session.query(
            day.label("day"),
            ScrapeAttempt.platform,
            ScrapeAttempt.domain,
            db.func.count().label("total"),
            db.func.sum(case((ScrapeAttempt.final_status == "complete", 1), else_=0)).label("complete"),
            db.func.sum(case((ScrapeAttempt.final_status == "partial", 1), else_=0)).label("partial"),
            db.func.sum(case((ScrapeAttempt.final_status == "failed", 1), else_=0)).label("failed"),
            db.func.sum(ScrapeAttempt.total_cost_usd).label("total_cost_usd"),
        ).filter(ScrapeAttempt.started_at >= since)

        if platform:
            query = query.filter(ScrapeAttempt.platform == platform)
        if domain:
            query = query.filter(ScrapeAttempt.domain == domain)

        return query.group_by(day, ScrapeAttempt.platform, ScrapeAttempt.domain).order_by(day.desc()).all()
