# Database model definitions for post model.
from sqlalchemy import inspect
from api import db


class PostMV(db.Model):
    """
    Read-only model backed by the `posts_mv` materialized view.
    Contains the latest snapshot per (page_id, platform, post_id).
    """
    __tablename__ = "posts_mv"

    # Composite PK mirrors the unique index on the MV.
    # Using String(36) for UUID — compatible with both PostgreSQL and SQLite.
    page_id     = db.Column(db.String(36), primary_key=True)
    platform    = db.Column(db.String(20), primary_key=True)
    post_id     = db.Column(db.String(100), primary_key=True)

    created_at  = db.Column(db.DateTime)
    recorded_at = db.Column(db.DateTime)   # timestamp of the source snapshot
    url         = db.Column(db.Text)

    likes       = db.Column(db.BigInteger)
    comments    = db.Column(db.BigInteger)
    shares      = db.Column(db.BigInteger)
    views       = db.Column(db.BigInteger)

    caption      = db.Column(db.Text)
    content_type = db.Column(db.String(50))
    image_url    = db.Column(db.Text)
    video_url    = db.Column(db.Text)
    is_pinned    = db.Column(db.Boolean)

    # Using db.JSON — compatible with both PostgreSQL and SQLite.
    extra_data   = db.Column(db.JSON)

    def to_dict(self):
        """Convert model instance to dictionary with all columns."""
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}

    def to_scraping_dict(self):
        """
        Convert to dictionary optimized for scraping service.
        Only includes fields needed by external scraper.
        """
        return {
            "url": self.url,
            "platform": self.platform,
            "comments": self.comments,
            "likes": self.likes,
            "content_type": self.content_type,
            "post_id": self.post_id,
            "page_id": self.page_id,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None
        }


class PostHistoryMV(db.Model):
    """
    Read-only model backed by the `posts_history_mv` materialized view.
    Contains every snapshot per (page_id, platform, post_id, recorded_at).
    """
    __tablename__ = "posts_history_mv"

    # Composite PK mirrors the unique index on the MV.
    page_id     = db.Column(db.String(36), primary_key=True)
    platform    = db.Column(db.String(20), primary_key=True)
    post_id     = db.Column(db.String(100), primary_key=True)
    recorded_at = db.Column(db.DateTime, primary_key=True)

    created_at  = db.Column(db.DateTime)
    url         = db.Column(db.Text)

    likes       = db.Column(db.BigInteger)
    comments    = db.Column(db.BigInteger)
    shares      = db.Column(db.BigInteger)
    views       = db.Column(db.BigInteger)

    caption      = db.Column(db.Text)
    content_type = db.Column(db.String(50))
    image_url    = db.Column(db.Text)
    video_url    = db.Column(db.Text)
    is_pinned    = db.Column(db.Boolean)

    extra_data   = db.Column(db.JSON)

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
