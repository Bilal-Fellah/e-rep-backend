from api import db
from sqlalchemy.orm import relationship

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

    # Self-referential relationship
    parent = relationship("Category", remote_side=[id], backref="subcategories")

    # Many-to-many with Entity
    entities = relationship("Entity", secondary="entity_category", back_populates="categories")
