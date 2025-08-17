from api import db
from api.models import Category

class CategoryRepository:
    @staticmethod   
    def get_by_id(category_id: int) -> Category | None:
        return Category.query.get(category_id)

    @staticmethod
    def get_all() -> list[Category]:
        return Category.query.all()

    @staticmethod
    def create(name: str, parent_id: int | None = None) -> Category:
        category = Category(name=name, parent_id=parent_id)
        db.session.add(category)
        db.session.commit()
        return category

    @staticmethod
    def update(category_id: int, **kwargs) -> Category | None:
        category = Category.query.get(category_id)
        if not category:
            return None
        for key, value in kwargs.items():
            setattr(category, key, value)
        db.session.commit()
        return category

    @staticmethod
    def delete(category_id: int) -> bool:
        category = Category.query.get(category_id)
        if not category:
            return False
        db.session.delete(category)
        db.session.commit()
        return True
