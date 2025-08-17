from api import db
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB


class PageHistory(db.Model):
    __tablename__ = "pages_history"

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey("pages.id"), nullable=False)
    data = db.Column(JSONB, nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    # Relationships
    page = relationship("Page", back_populates="histories")
