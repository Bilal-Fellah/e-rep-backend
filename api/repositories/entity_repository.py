from api import db
from api.models import Entity
from api.models.page_history_model import PageHistory
from api.models.page_model import Page
from sqlalchemy import text

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
    def get_who_has_history() -> list[Entity]:
        
        return (
            Entity.query
            .join(Page, Page.entity_id == Entity.id)
            .join(PageHistory, PageHistory.page_id == Page.uuid)
            .distinct()
            .all()
        )
    
    @staticmethod
    def change_to_scrape(entity_id: int, to_scrape: bool) -> Entity | None:
        entity = Entity.query.get(entity_id)
        if not entity:
            return None
        entity.to_scrape = to_scrape
        db.session.commit()
        return entity

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

    @staticmethod
    def get_entity_posts_metrics(entity_id: int, date_limit: str):
        query = text("""
            SELECT * from page_posts_metrics_mv
            where platform in ('instagram','linkedin','tiktok','youtube','x')
            and entity_id = :entity_id
            and to_scrape
                    """)
        results = db.session.execute(query, {'entity_id': entity_id}).all()
        return results