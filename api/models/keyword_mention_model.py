# Database model definitions for keyword mention model.
#
# One row per TikTok video the keyword-search pass matched against a client's
# tracked keyword (api/models/tracked_keyword_model.py). Re-searching the same
# keyword on a later pass is expected and idempotent: the unique constraint on
# (keyword_id, video_id) means a video already recorded is silently skipped,
# not duplicated -- see KeywordMentionRepository.bulk_insert_ignore_duplicates.
from api import db


class KeywordMention(db.Model):
    __tablename__ = "keyword_mentions"

    id = db.Column(db.Integer, primary_key=True)

    keyword_id = db.Column(
        db.Integer,
        db.ForeignKey("tracked_keywords.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform = db.Column(db.String(20), nullable=False)
    video_id = db.Column(db.String(64), nullable=False)
    video_url = db.Column(db.Text, nullable=False)

    author_username = db.Column(db.String(120), nullable=True)
    caption = db.Column(db.Text, nullable=True)
    thumbnail_url = db.Column(db.Text, nullable=True)

    # Best-effort -- whatever the search results page itself shows, not a
    # follow-up fetch of the video. May be null if TikTok didn't render it.
    like_count = db.Column(db.Integer, nullable=True)
    comment_count = db.Column(db.Integer, nullable=True)

    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    discovered_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("keyword_id", "video_id", name="uq_keyword_mentions_keyword_video"),
    )
