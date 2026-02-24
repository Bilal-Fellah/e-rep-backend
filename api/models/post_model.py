from sqlalchemy import inspect
from api import db
from sqlalchemy.dialects.postgresql import UUID, JSONB


class PostMV(db.Model):
    """
    Read-only model backed by the `posts_mv` materialized view.
    Contains the latest snapshot per (page_id, platform, post_id).
    """
    __tablename__ = "posts_mv"

    # Composite PK mirrors the unique index on the MV.
    page_id     = db.Column(UUID(as_uuid=True), primary_key=True)
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

    extra_data   = db.Column(JSONB)

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


class PostHistoryMV(db.Model):
    """
    Read-only model backed by the `posts_history_mv` materialized view.
    Contains every snapshot per (page_id, platform, post_id, recorded_at).
    """
    __tablename__ = "posts_history_mv"

    # Composite PK mirrors the unique index on the MV.
    page_id     = db.Column(UUID(as_uuid=True), primary_key=True)
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

    extra_data   = db.Column(JSONB)

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
