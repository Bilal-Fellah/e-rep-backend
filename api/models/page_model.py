from api import db
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid



class Page(db.Model):
    __tablename__ = "pages"

    name = db.Column(db.Text, nullable=False)
    link = db.Column(db.Text, unique=True, nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    entity_id = db.Column(db.Integer, db.ForeignKey("entities.id"), nullable=False)
    uuid = db.Column(UUID(as_uuid=True), unique=True, primary_key = True, nullable=False, default=uuid.uuid4)


    __table_args__ = (
        CheckConstraint(platform.in_(["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"])),
    )

    # Relationships
    entity = relationship("Entity", back_populates="pages")
    histories = relationship("PageHistory", back_populates="page", cascade="all, delete-orphan")

    @staticmethod
    def generate_uuid(link, platform=None):
        base_str = f"{link}{platform or ''}"
        return uuid.uuid5(uuid.NAMESPACE_DNS, base_str)
