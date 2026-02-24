from datetime import datetime, timezone
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSON
from api import db

class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)

    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.String(50), nullable=False)

    context_data = db.Column(JSON, nullable=True)

    visibility = db.Column(
        db.String(20),
        nullable=False,
        default="private"
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active"   # active | archived | deleted
    )

    created_at = db.Column(
        db.DateTime, default=datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc)
    )

    author = db.relationship("User", backref="notes")

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}