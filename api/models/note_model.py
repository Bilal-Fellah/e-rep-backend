from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON

db = SQLAlchemy()

class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)

    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)

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
