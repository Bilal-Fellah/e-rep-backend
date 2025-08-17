from api import db
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship

class Entity(db.Model):
    __tablename__ = "entities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    type = db.Column(db.String(20), nullable=False)

    __table_args__ = (
        CheckConstraint(type.in_(["company", "influencer", "small-business"])),
    )

    pages = relationship("Page", back_populates="entity", cascade="all, delete-orphan")
    categories = relationship("Category", secondary="entity_category", back_populates="entities")
