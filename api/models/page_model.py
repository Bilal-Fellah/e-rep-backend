from api import db
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship

class Page(db.Model):
    __tablename__ = "pages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    link = db.Column(db.Text, unique=True, nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    entity_id = db.Column(db.Integer, db.ForeignKey("entities.id"), nullable=False)

    __table_args__ = (
        CheckConstraint(platform.in_(["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"])),
    )

    # Relationships
    entity = relationship("Entity", back_populates="pages")
    histories = relationship("PageHistory", back_populates="page", cascade="all, delete-orphan")
