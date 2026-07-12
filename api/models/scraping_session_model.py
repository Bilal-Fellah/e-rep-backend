# Database model definitions for scraping session model.
import uuid
from datetime import datetime
from sqlalchemy import inspect
from sqlalchemy.orm import relationship
from api import db


class ScrapingSession(db.Model):
    """
    Model for tracking scraping sessions with metadata and status.
    Provides audit trail for all scraping operations.
    """
    __tablename__ = "scraping_sessions"
    
    # Primary Key (UUID)
    session_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Tracking Metrics
    posts_fetched = db.Column(db.Integer, default=0, nullable=False)
    comments_inserted = db.Column(db.Integer, default=0, nullable=False)
    
    # Status Tracking (pending, completed, failed)
    status = db.Column(db.String(20), default="pending", nullable=False)
    
    # Error Handling
    error_message = db.Column(db.Text, nullable=True)
    
    # Relationships
    comments = relationship("Comment", backref="scraping_session", passive_deletes=True)
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint("status IN ('pending', 'completed', 'failed')", 
                          name='ck_session_status'),
    )
    
    def to_dict(self):
        """Convert model instance to dictionary."""
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
