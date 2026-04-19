# Data-access methods for entity category repository.
from api import db
from api.models import EntityCategory
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class EntityCategoryRepository:
    @staticmethod
    def add(entity_id: int, category_id: int, commit: bool = True):
        new_relation = EntityCategory(entity_id=entity_id, category_id=category_id)
        db.session.add(new_relation)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return new_relation

    @staticmethod
    def get_all():
        return EntityCategory.query.all()

    @staticmethod
    def get_by_entity(entity_id: int):
        return EntityCategory.query.filter_by(entity_id=entity_id).all()

    @staticmethod
    def delete(entity_id: int, category_id: int):
        relation = EntityCategory.query.filter_by(
            entity_id=entity_id, category_id=category_id
        ).first()
        if relation:
            db.session.delete(relation)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def delete_by_entity(entity_id: int):
        relation = EntityCategory.query.filter_by(
            entity_id=entity_id
        ).first()
        if relation:
            db.session.delete(relation)
            db.session.commit()
            return True
        return False
