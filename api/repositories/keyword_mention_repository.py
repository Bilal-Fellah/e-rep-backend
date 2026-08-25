# Data-access methods for keyword mention repository.
from api.models.keyword_mention_model import KeywordMention, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class KeywordMentionRepository:
    """Repository for keyword_mentions database operations."""

    @staticmethod
    def exists(keyword_id: int, video_id: str) -> bool:
        return db.session.query(
            KeywordMention.query.filter_by(keyword_id=keyword_id, video_id=video_id).exists()
        ).scalar()

    @staticmethod
    def bulk_insert_ignore_duplicates(keyword_id: int, platform: str, mentions: list[dict]) -> int:
        """Insert every mention not already recorded for this keyword
        (matched by video_id -- see uq_keyword_mentions_keyword_video).
        Check-then-insert rather than a DB-level upsert, matching how
        CommentRepository dedupes elsewhere in this codebase; safe here
        because only one keyword-search pass runs at a time (the VPS side
        serializes all scraper runs through one flock lock).

        Returns the number of rows actually inserted.
        """
        inserted = 0
        for m in mentions:
            video_id = m.get("video_id")
            if not video_id:
                continue
            if KeywordMentionRepository.exists(keyword_id, video_id):
                continue
            db.session.add(
                KeywordMention(
                    keyword_id=keyword_id,
                    platform=platform,
                    video_id=video_id,
                    video_url=m.get("video_url"),
                    author_username=m.get("author_username"),
                    caption=m.get("caption"),
                    thumbnail_url=m.get("thumbnail_url"),
                    like_count=m.get("like_count"),
                    comment_count=m.get("comment_count"),
                    posted_at=m.get("posted_at"),
                )
            )
            inserted += 1
        if inserted:
            db.session.commit()
        return inserted

    @staticmethod
    def count_for_keyword(keyword_id: int) -> int:
        return KeywordMention.query.filter_by(keyword_id=keyword_id).count()

    @staticmethod
    def list_for_keyword(keyword_id: int, limit: int = 50, offset: int = 0) -> list[KeywordMention]:
        return (
            KeywordMention.query.filter_by(keyword_id=keyword_id)
            .order_by(KeywordMention.discovered_at.desc(), KeywordMention.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
