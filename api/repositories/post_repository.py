# Data-access methods for post repository.
import logging
from datetime import datetime, timedelta

from sqlalchemy import case, select, text

from api.models.post_model import db, PostMV, PostHistoryMV
from api.models.page_model import Page
from api.models.page_history_model import PageHistory
from api.utils.logging_utils import instrument_repository_class

logger = logging.getLogger(__name__)


@instrument_repository_class
class PostRepository:

    # ── Single post lookup ────────────────────────────────────────────────

    @staticmethod
    def get_by_id(post_id) -> PostMV | None:
        """Fetch one post by its ID from posts_mv."""
        return PostMV.query.filter_by(
            post_id=str(post_id)
        ).first()
    
    
    @staticmethod
    def get_by_composite_key(page_id, platform, post_id) -> PostMV | None:
        """Fetch one post by its composite key from posts_mv."""
        return PostMV.query.filter_by(
            page_id=page_id,
            platform=platform,
            post_id=post_id
        ).first()

    # ── List queries ──────────────────────────────────────────────────────

    @staticmethod
    def get_by_platform(platform: str) -> list[PostMV]:
        """All latest posts for a given platform."""
        return PostMV.query.filter_by(platform=platform).all()

    @staticmethod
    def get_by_page(page_id, platform: str | None = None) -> list[PostMV]:
        """All latest posts for a page, optionally filtered by platform."""
        q = PostMV.query.filter_by(page_id=page_id)
        if platform:
            q = q.filter_by(platform=platform)
        return q.order_by(PostMV.created_at.desc()).all()

    @staticmethod
    def get_by_entity(entity_id: int, platform: str | None = None) -> list[PostMV]:
        """All latest posts for every page belonging to an entity."""
        q = (
            db.session.query(PostMV)
            .join(Page, Page.uuid == PostMV.page_id)
            .filter(Page.entity_id == entity_id)
        )
        if platform:
            q = q.filter(PostMV.platform == platform)
        return q.order_by(PostMV.created_at.desc()).all()

    # ── History ───────────────────────────────────────────────────────────

    @staticmethod
    def get_post_history(page_id, platform: str, post_id: str) -> list[PostHistoryMV]:
        """Full time-series snapshots for one post from posts_history_mv."""
        return (
            PostHistoryMV.query
            .filter_by(page_id=page_id, platform=platform, post_id=post_id)
            .order_by(PostHistoryMV.recorded_at.desc())
            .all()
        )

    # ── Materialized view refresh ───────────────────────────────────────

    @staticmethod
    def refresh_post_views():
        """Refresh posts_history_mv then posts_mv (posts_mv is DISTINCT ON
        posts_history_mv, so it must go second) after a post-metric
        correction writes directly to the underlying pages_history row.

        Best-effort: the correction itself already committed by the time
        this runs, so a refresh failure must never surface as a failed
        request. Unlike page_posts_metrics_mv, these two views have no
        existing scheduled refresh anywhere in this codebase (see the
        "Run this after every scrape cycle (or on a schedule)" note in
        api/database/posts_mv_queries.sql — that's handled externally,
        e.g. by the DB server, not by `flask refresh-mv`, which only
        touches page_posts_metrics_mv). So on failure here they simply
        stay stale until that external refresh runs, or until another
        post_metric correction succeeds. This also means it's a no-op
        under SQLite (the dev/test DB) — REFRESH MATERIALIZED VIEW isn't
        a concept there, which is expected.
        """
        try:
            db.session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY posts_history_mv"))
            db.session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY posts_mv"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(text("REFRESH MATERIALIZED VIEW posts_history_mv"))
                db.session.execute(text("REFRESH MATERIALIZED VIEW posts_mv"))
                db.session.commit()
            except Exception:
                db.session.rollback()
                logger.warning(
                    "post-metric correction committed but posts_mv/posts_history_mv "
                    "refresh failed; these views have no other scheduled refresh, "
                    "so they'll stay stale until the next successful post_metric "
                    "correction or a manual REFRESH.",
                    exc_info=True,
                )

    # ── Data integrity ───────────────────────────────────────────────────
    # Null-rate reporting for the admin "Data Integrity" panel. Built with
    # portable SQLAlchemy case()/count() rather than Postgres FILTER: since
    # PostMV/PostHistoryMV are declared as ordinary db.Model classes,
    # db.create_all() creates them as plain tables under the SQLite
    # test/dev DB, and this style of query runs unchanged against them.

    @staticmethod
    def get_metric_integrity_by_platform() -> list:
        null_likes = db.func.sum(case((PostMV.likes.is_(None), 1), else_=0))
        null_comments = db.func.sum(case((PostMV.comments.is_(None), 1), else_=0))
        null_shares = db.func.sum(case((PostMV.shares.is_(None), 1), else_=0))
        return (
            db.session.query(
                PostMV.platform,
                db.func.count().label("total"),
                null_likes.label("null_likes"),
                null_comments.label("null_comments"),
                null_shares.label("null_shares"),
            )
            .group_by(PostMV.platform)
            .all()
        )

    @staticmethod
    def get_metric_integrity_daily(days: int = 14) -> list:
        since = datetime.now() - timedelta(days=days)
        day = db.func.date(PostHistoryMV.recorded_at)
        null_likes = db.func.sum(case((PostHistoryMV.likes.is_(None), 1), else_=0))
        null_comments = db.func.sum(case((PostHistoryMV.comments.is_(None), 1), else_=0))
        null_shares = db.func.sum(case((PostHistoryMV.shares.is_(None), 1), else_=0))
        return (
            db.session.query(
                day.label("day"),
                PostHistoryMV.platform,
                db.func.count().label("total"),
                null_likes.label("null_likes"),
                null_comments.label("null_comments"),
                null_shares.label("null_shares"),
            )
            .filter(PostHistoryMV.recorded_at >= since)
            .group_by(day, PostHistoryMV.platform)
            .order_by(day.desc())
            .all()
        )

    @staticmethod
    def get_metric_integrity_samples(limit: int = 5) -> list:
        """A handful of the latest posts missing likes or comments — the
        two metrics every platform tracks — so the admin UI can hand back
        a ready-to-use post_metric correction target. Recovers the
        pages_history.id half of that composite target id (posts_mv only
        carries page_id + recorded_at) via a scalar subquery rather than a
        join: nothing in the schema guarantees at most one pages_history
        row per (page_id, recorded_at), so a plain join could fan out and
        misattribute the target id if a duplicate timestamp ever exists.
        MIN(id) keeps this deterministic either way."""
        page_history_id = (
            select(db.func.min(PageHistory.id))
            .where(PageHistory.page_id == PostMV.page_id, PageHistory.recorded_at == PostMV.recorded_at)
            .correlate(PostMV)
            .scalar_subquery()
        )
        return (
            db.session.query(
                page_history_id.label("page_history_id"),
                PostMV.post_id,
                PostMV.platform,
                Page.name.label("page_name"),
                PostMV.recorded_at,
                PostMV.likes,
                PostMV.comments,
                PostMV.shares,
                PostMV.url,
                PostMV.caption,
            )
            .select_from(PostMV)
            .join(Page, Page.uuid == PostMV.page_id)
            .filter((PostMV.likes.is_(None)) | (PostMV.comments.is_(None)))
            .order_by(PostMV.recorded_at.desc())
            .limit(limit)
            .all()
        )
