from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from sqlalchemy import inspect
from api import db
from sqlalchemy.dialects.postgresql import UUID, JSONB


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.BigInteger, primary_key=True)
    page_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pages.uuid"), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    post_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    url = db.Column(db.Text)
    
    likes = db.Column(db.BigInteger)
    comments = db.Column(db.BigInteger)
    shares = db.Column(db.BigInteger)
    views = db.Column(db.BigInteger)

    caption = db.Column(db.Text)
    content_type = db.Column(db.String(50))
    image_url = db.Column(db.Text)
    video_url = db.Column(db.Text)
    is_pinned = db.Column(db.Boolean)

    extra_data = db.Column(JSONB, nullable=True)

    # Ensure uniqueness per platform/page/post
    __table_args__ = (db.UniqueConstraint("page_id", "platform", "post_id", name="uix_post_platform_page"),)

    # Relationship to history
    history = db.relationship("PostHistory", backref="post", lazy="dynamic")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


class PostHistory(db.Model):
    __tablename__ = "posts_history"

    id = db.Column(db.BigInteger, primary_key=True)
    post_id = db.Column(db.BigInteger, db.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    likes = db.Column(db.BigInteger)
    comments = db.Column(db.BigInteger)
    shares = db.Column(db.BigInteger)
    views = db.Column(db.BigInteger)
    extra_data = db.Column(JSONB, nullable=True)
