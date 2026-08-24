# Data-access methods for tracked keyword repository.
from api.models.tracked_keyword_model import TrackedKeyword, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class TrackedKeywordRepository:
    """Repository for tracked_keywords database operations."""

    @staticmethod
    def list_for_user(user_id: int) -> list[TrackedKeyword]:
        return (
            TrackedKeyword.query.filter_by(user_id=user_id)
            .order_by(TrackedKeyword.created_at.asc(), TrackedKeyword.id.asc())
            .all()
        )

    @staticmethod
    def count_for_user(user_id: int) -> int:
        return TrackedKeyword.query.filter_by(user_id=user_id).count()

    @staticmethod
    def get_by_id(keyword_id: int) -> TrackedKeyword | None:
        return db.session.get(TrackedKeyword, keyword_id)

    @staticmethod
    def create(user_id: int, platform: str, keyword: str, commit: bool = True) -> TrackedKeyword:
        row = TrackedKeyword(user_id=user_id, platform=platform, keyword=keyword)
        db.session.add(row)
        if commit:
            db.session.commit()
        return row

    @staticmethod
    def delete(row: TrackedKeyword, commit: bool = True) -> None:
        db.session.delete(row)
        if commit:
            db.session.commit()

    @staticmethod
    def list_for_platform(platform: str) -> list[TrackedKeyword]:
        """Every currently tracked keyword for `platform`, across all users --
        what the VPS keyword-search pass fetches each scheduled run. No
        claim/lock semantics needed here (unlike scrape_trigger_requests):
        re-searching the same keyword on every pass is expected and cheap to
        dedupe on the mentions side."""
        return TrackedKeyword.query.filter_by(platform=platform).all()
