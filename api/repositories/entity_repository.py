from api import db
from api.models import Entity

class EntityRepository:
    @staticmethod
    def get_by_id(entity_id: int) -> Entity | None:
        return Entity.query.get(entity_id)
    
    @staticmethod
    def get_by_name(entity_name: str) -> Entity | None:
        return Entity.query.filter_by(name=entity_name).first()

    @staticmethod
    def get_all() -> list[Entity]:
        return Entity.query.all()

    @staticmethod
    def create(name: str, type_: str) -> Entity:
        entity = Entity(name=name, type=type_)
        db.session.add(entity)
        db.session.commit()
        return entity

    @staticmethod
    def update(entity_id: int, **kwargs) -> Entity | None:
        entity = Entity.query.get(entity_id)
        if not entity:
            return None
        for key, value in kwargs.items():
            setattr(entity, key, value)
        db.session.commit()
        return entity

    @staticmethod
    def delete(entity_id: int) -> bool:
        entity = Entity.query.get(entity_id)
        if not entity:
            return False
        db.session.delete(entity)
        db.session.commit()
        return True
