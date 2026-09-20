# Data-access methods for priority entity repository.
#
# Two jobs: membership of the priority list itself (a small CRUD table),
# and the batched read queries behind the deeper per-page validity check
# the Priority page runs over those entities. The check queries are all
# grouped by page and take a list of page ids, so checking N clients is a
# fixed handful of queries rather than N x per-page round-trips.
from datetime import datetime

from sqlalchemy import case, select

from api.models.entity_model import Entity
from api.models.page_model import Page
from api.models.page_history_model import PageHistory
from api.models.post_model import PostMV
from api.models.priority_entity_model import PriorityEntity, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class PriorityEntityRepository:
    """Repository for priority_entities plus the per-entity data checks."""

    # ── Membership ────────────────────────────────────────────────────────

    @staticmethod
    def list_all() -> list:
        """Every priority entity joined to its brand row, newest first."""
        return (
            db.session.query(
                PriorityEntity.id,
                PriorityEntity.entity_id,
                PriorityEntity.label,
                PriorityEntity.note,
                PriorityEntity.added_by,
                PriorityEntity.created_at,
                Entity.name.label("entity_name"),
                Entity.type.label("entity_type"),
                Entity.to_scrape.label("to_scrape"),
            )
            .join(Entity, Entity.id == PriorityEntity.entity_id)
            .order_by(PriorityEntity.created_at.desc(), PriorityEntity.id.desc())
            .all()
        )

    @staticmethod
    def get_by_entity_id(entity_id: int) -> PriorityEntity | None:
        return PriorityEntity.query.filter_by(entity_id=entity_id).first()

    @staticmethod
    def create(
        entity_id: int,
        label: str | None,
        note: str | None,
        added_by: int | None,
        commit: bool = True,
    ) -> PriorityEntity:
        row = PriorityEntity(entity_id=entity_id, label=label, note=note, added_by=added_by)
        db.session.add(row)
        if commit:
            db.session.commit()
        return row

    @staticmethod
    def update(row: PriorityEntity, commit: bool = True, **kwargs) -> PriorityEntity:
        for key, value in kwargs.items():
            if value is not None and hasattr(row, key):
                setattr(row, key, value)
        if commit:
            db.session.commit()
        return row

    @staticmethod
    def delete(row: PriorityEntity, commit: bool = True) -> None:
        db.session.delete(row)
        if commit:
            db.session.commit()

    # ── Data checks ───────────────────────────────────────────────────────

    @staticmethod
    def get_pages_for_entities(entity_ids: list[int]) -> list:
        """Every tracked page belonging to any of these entities."""
        if not entity_ids:
            return []
        return (
            db.session.query(
                Page.uuid,
                Page.name,
                Page.link,
                Page.platform,
                Page.entity_id,
            )
            .filter(Page.entity_id.in_(entity_ids))
            .order_by(Page.entity_id, Page.platform, Page.name)
            .all()
        )

    @staticmethod
    def get_latest_history_for_pages(page_ids: list) -> list:
        """The most recent pages_history row for each of these pages.

        Uses a max(recorded_at)-per-page subquery joined back to the table
        rather than Postgres' DISTINCT ON, so the same query also runs on
        the SQLite test database. Nothing in the schema guarantees one row
        per (page_id, recorded_at), so a tie can still return two rows for
        a page -- the service keeps the highest id and drops the rest.
        """
        if not page_ids:
            return []
        latest = (
            select(
                PageHistory.page_id.label("page_id"),
                db.func.max(PageHistory.recorded_at).label("max_recorded_at"),
            )
            .where(PageHistory.page_id.in_(page_ids))
            .group_by(PageHistory.page_id)
            .subquery()
        )
        return (
            db.session.query(
                PageHistory.id,
                PageHistory.page_id,
                PageHistory.recorded_at,
                PageHistory.data,
                PageHistory.source,
            )
            .join(
                latest,
                (PageHistory.page_id == latest.c.page_id)
                & (PageHistory.recorded_at == latest.c.max_recorded_at),
            )
            .all()
        )

    @staticmethod
    def count_history_since(page_ids: list, since: datetime) -> list:
        """Snapshot count per page since `since`, plus how many distinct
        days those snapshots cover -- a page can be scraped five times in
        one day and not at all on the other four."""
        if not page_ids:
            return []
        return (
            db.session.query(
                PageHistory.page_id,
                db.func.count().label("snapshots"),
                db.func.count(db.distinct(db.func.date(PageHistory.recorded_at))).label("days_covered"),
            )
            .filter(PageHistory.page_id.in_(page_ids), PageHistory.recorded_at >= since)
            .group_by(PageHistory.page_id)
            .all()
        )

    @staticmethod
    def get_post_stats_for_pages(page_ids: list) -> list:
        """Current post counts and null-metric counts per page, from the
        posts_mv snapshot (latest row per post), matching how the
        fleet-wide Data Integrity report measures the same thing."""
        if not page_ids:
            return []
        keys = [str(pid) for pid in page_ids]
        null_likes = db.func.sum(case((PostMV.likes.is_(None), 1), else_=0))
        null_comments = db.func.sum(case((PostMV.comments.is_(None), 1), else_=0))
        return (
            db.session.query(
                PostMV.page_id,
                db.func.count().label("total"),
                null_likes.label("null_likes"),
                null_comments.label("null_comments"),
                db.func.max(PostMV.recorded_at).label("last_recorded_at"),
            )
            .filter(PostMV.page_id.in_(keys))
            .group_by(PostMV.page_id)
            .all()
        )

    @staticmethod
    def count_posts_since(page_ids: list, since: datetime) -> list:
        """Posts whose latest snapshot landed after `since` -- the posts-side
        half of "did the run I just fired actually bring anything back for
        this client"."""
        if not page_ids:
            return []
        keys = [str(pid) for pid in page_ids]
        return (
            db.session.query(
                PostMV.page_id,
                db.func.count().label("posts"),
            )
            .filter(PostMV.page_id.in_(keys), PostMV.recorded_at >= since)
            .group_by(PostMV.page_id)
            .all()
        )
