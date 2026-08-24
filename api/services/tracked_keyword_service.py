# Service layer for the client-owned keyword watchlist and the mentions the
# VPS keyword-search pass finds against it. See api/models/tracked_keyword_model.py
# and api/models/keyword_mention_model.py.
from datetime import datetime

from api.repositories.tracked_keyword_repository import TrackedKeywordRepository
from api.repositories.keyword_mention_repository import KeywordMentionRepository
from api.utils.logging_utils import instrument_service_class

# A client can track at most this many keywords at once. Deliberately small
# and enforced here (not just a UI limit) -- every tracked keyword is a
# recurring TikTok search on a shared, rate-limited scraper session, not a
# free-form filter over already-fetched data.
MAX_KEYWORDS_PER_USER = 3

# Only TikTok has a keyword-search capability today (tiktok_scraper's search
# mode on the VPS). A second platform is an allowlist change here, not a
# migration -- the column already supports it.
SUPPORTED_PLATFORMS = ("tiktok",)

MAX_KEYWORD_LENGTH = 120


class TrackedKeywordError(ValueError):
    """Raised for an invalid keyword, an unsupported platform, or the
    per-user limit."""


@instrument_service_class
class TrackedKeywordService:
    # ------------------------------------------------------------------
    # Client-facing (JWT-gated data routes)
    # ------------------------------------------------------------------
    @staticmethod
    def list_for_user(user_id: int) -> list[dict]:
        return [
            TrackedKeywordService._serialize(row)
            for row in TrackedKeywordRepository.list_for_user(user_id)
        ]

    @staticmethod
    def create(user_id: int, payload: dict) -> dict:
        keyword = (payload.get("keyword") or "").strip()
        platform = (payload.get("platform") or "tiktok").strip().lower()

        if not keyword:
            raise TrackedKeywordError("keyword is required")
        if len(keyword) > MAX_KEYWORD_LENGTH:
            raise TrackedKeywordError(f"keyword must be at most {MAX_KEYWORD_LENGTH} characters")
        if platform not in SUPPORTED_PLATFORMS:
            raise TrackedKeywordError(f"platform must be one of {SUPPORTED_PLATFORMS}")

        existing = TrackedKeywordRepository.list_for_user(user_id)
        if len(existing) >= MAX_KEYWORDS_PER_USER:
            raise TrackedKeywordError(
                f"You can track at most {MAX_KEYWORDS_PER_USER} keywords -- remove one first"
            )
        if any(row.platform == platform and row.keyword.lower() == keyword.lower() for row in existing):
            raise TrackedKeywordError("You're already tracking this keyword")

        row = TrackedKeywordRepository.create(user_id, platform, keyword)
        return TrackedKeywordService._serialize(row)

    @staticmethod
    def delete(user_id: int, keyword_id: int) -> bool:
        row = TrackedKeywordRepository.get_by_id(keyword_id)
        if row is None or row.user_id != user_id:
            return False
        TrackedKeywordRepository.delete(row)
        return True

    @staticmethod
    def list_mentions(user_id: int, keyword_id: int, limit: int = 50, offset: int = 0) -> list[dict] | None:
        """None means "not found or not yours" -- the route turns that into a 404."""
        row = TrackedKeywordRepository.get_by_id(keyword_id)
        if row is None or row.user_id != user_id:
            return None
        return [
            TrackedKeywordService._serialize_mention(m)
            for m in KeywordMentionRepository.list_for_keyword(keyword_id, limit, offset)
        ]

    # ------------------------------------------------------------------
    # Admin-facing (Brendex Admin, support/debugging visibility)
    # ------------------------------------------------------------------
    @staticmethod
    def list_all_for_admin(platform: str = "tiktok") -> list[dict]:
        rows = []
        for row in TrackedKeywordRepository.list_for_platform(platform):
            serialized = TrackedKeywordService._serialize(row)
            serialized["mention_count"] = KeywordMentionRepository.count_for_keyword(row.id)
            rows.append(serialized)
        return rows

    # ------------------------------------------------------------------
    # VPS-facing (api-key-gated engine routes)
    # ------------------------------------------------------------------
    @staticmethod
    def list_keywords_for_platform(platform: str) -> list[dict]:
        return [
            TrackedKeywordService._serialize(row)
            for row in TrackedKeywordRepository.list_for_platform(platform)
        ]

    @staticmethod
    def record_mentions(keyword_id: int, mentions: list[dict]) -> int:
        row = TrackedKeywordRepository.get_by_id(keyword_id)
        if row is None:
            raise TrackedKeywordError(f"No tracked keyword with id {keyword_id}.")

        # video_id/video_url are the only truly required fields -- everything
        # else (caption, author, counts) is best-effort scrape output and may
        # legitimately be missing.
        clean = []
        for m in mentions:
            if not (m.get("video_id") and m.get("video_url")):
                continue
            m = dict(m)
            m["posted_at"] = TrackedKeywordService._parse_iso(m.get("posted_at"))
            clean.append(m)
        return KeywordMentionRepository.bulk_insert_ignore_duplicates(row.id, row.platform, clean)

    @staticmethod
    def _parse_iso(raw) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None

    # ------------------------------------------------------------------
    @staticmethod
    def _serialize(row) -> dict:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "platform": row.platform,
            "keyword": row.keyword,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _serialize_mention(row) -> dict:
        return {
            "id": row.id,
            "keyword_id": row.keyword_id,
            "platform": row.platform,
            "video_id": row.video_id,
            "video_url": row.video_url,
            "author_username": row.author_username,
            "caption": row.caption,
            "thumbnail_url": row.thumbnail_url,
            "like_count": row.like_count,
            "comment_count": row.comment_count,
            "posted_at": row.posted_at.isoformat() if row.posted_at else None,
            "discovered_at": row.discovered_at.isoformat() if row.discovered_at else None,
        }
