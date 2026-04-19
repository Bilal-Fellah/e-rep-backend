# Database model definitions for entity category model.

from api import db

class EntityCategory(db.Model):
    __tablename__ = "entity_category"

    entity_id = db.Column(db.Integer, db.ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True)
