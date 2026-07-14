# Database model definitions for scraping post result model.
from datetime import datetime
from sqlalchemy import inspect
from api import db


class ScrapingPostResult(db.Model):
    """
    Records the outcome of scraping a specific post during a session.
    One row per (page_id, platform, post_id, scraping_session_id) attempt.
    
    This is what distinguishes:
    - comments_count = 0  → post was scraped, had no comments (done)
    - no row at all       → post was never scraped (pending)
    """
    __tablename__ = "scraping_post_results"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Post identification
    page_id  = db.Column(db.String(36), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    post_id  = db.Column(db.String(100), nullable=False)

    # Session reference
    scraping_session_id = db.Column(
        db.String(36),
        db.ForeignKey("scraping_sessions.session_id", ondelete="SET NULL"),
        nullable=True
    )

    # Outcome — how many comments were inserted for this post in this run
    comments_count = db.Column(db.Integer, nullable=False, default=0)

    # Timestamp when this result was recorded
    scraped_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Constraints & indexes
    __table_args__ = (
        db.UniqueConstraint(
            'page_id', 'platform', 'post_id', 'scraping_session_id',
            name='uq_scraping_post_result'
        ),
        db.Index('ix_spr_post_lookup', 'page_id', 'platform', 'post_id'),
        db.Index('ix_spr_scraped_at', 'scraped_at'),
        db.Index('ix_spr_session', 'scraping_session_id'),
    )

    def to_dict(self):
        """Convert model instance to dictionary."""
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
