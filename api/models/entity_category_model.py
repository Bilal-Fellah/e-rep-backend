
from api import db

class EntityCategory(db.Model):
    __tablename__ = "entity_category"

    entity_id = db.Column(db.Integer, db.ForeignKey("entities.id"), primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), primary_key=True)
