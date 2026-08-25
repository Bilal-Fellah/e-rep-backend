# Database model definitions for tracked keyword model.
#
# A client-owned watchlist: up to TrackedKeywordService.MAX_KEYWORDS_PER_USER
# freeform keywords per user (brand name, aliases, a competitor, ...), not
# tied to any entity in the entities table -- these are the client's own
# words to watch, not a system-managed concept. A scheduled VPS pass
# (tiktok_scraper's keyword-search mode) searches TikTok for each one and
# reports matches back as KeywordMention rows. See tracked_keyword_service.py
# for the per-user cap and api/docs/keyword_mentions.md for the API shape.
from api import db


class TrackedKeyword(db.Model):
    __tablename__ = "tracked_keywords"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Only "tiktok" is actually searched today (ScraperCredentialService's
    # SUPPORTED_PLATFORMS-style single-platform start) -- kept as a column
    # rather than hardcoded so a second platform is a service-layer allowlist
    # change, not a migration.
    platform = db.Column(db.String(20), nullable=False, default="tiktok")
    keyword = db.Column(db.String(120), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "platform", "keyword", name="uq_tracked_keywords_user_platform_keyword"
        ),
    )
