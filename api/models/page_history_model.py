from api import db
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID


class PageHistory(db.Model):
    __tablename__ = "pages_history"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data = db.Column(JSONB, nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    page_id = db.Column(UUID(as_uuid=True), db.ForeignKey("pages.uuid"))

    # relationship to Page (optional, if you want ORM navigation)
    page = relationship("Page", back_populates="histories", foreign_keys=[page_id])
