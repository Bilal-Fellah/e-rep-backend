# Database model definitions for comment model.
from datetime import datetime
from sqlalchemy import inspect
from api import db


class Comment(db.Model):
    """
    Model for storing scraped comments from social media posts.
    Tracks comments with platform-specific metadata and relationships.
    """
    __tablename__ = "comments"
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Composite Foreign Key to Post (page_id, platform, post_id)
    page_id = db.Column(db.String(36), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    post_id = db.Column(db.String(100), nullable=False)
    
    # Comment Identification (platform's comment ID)
    comment_id = db.Column(db.String(100), nullable=False)
    
    # Comment Content
    text = db.Column(db.Text, nullable=False)
    
    # Author Information
    author_username = db.Column(db.String(100), nullable=True)
    author_profile_url = db.Column(db.Text, nullable=True)
    
    # Timestamps
    comment_timestamp = db.Column(db.DateTime, nullable=False)  # When comment was posted
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Metrics
    likes_count = db.Column(db.BigInteger, default=0, nullable=False)
    replies_count = db.Column(db.BigInteger, default=0, nullable=False)
    
    # Nested Comments Support
    parent_comment_id = db.Column(db.String(100), nullable=True)
    
    # Session Tracking
    scraping_session_id = db.Column(
        db.String(36), 
        db.ForeignKey("scraping_sessions.session_id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Platform-Specific Metadata
    extra_data = db.Column(db.JSON, nullable=True)
    
    # Label (classification result from inference, values 0-4)
    label = db.Column(db.Integer, nullable=True)
    
    # Constraints and Indexes
    __table_args__ = (
        db.UniqueConstraint('page_id', 'platform', 'post_id', 'comment_id', 
                           name='uq_comment_composite'),
        db.Index('ix_comment_post_lookup', 'page_id', 'platform', 'post_id'),
        db.Index('ix_comment_session', 'scraping_session_id'),
    )
    
    def to_dict(self):
        """Convert model instance to dictionary."""
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
