from api.models.post_model import db, PostMV, PostHistoryMV
from api.models.page_model import Page
from api.models.entity_model import Entity
from sqlalchemy import select


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
