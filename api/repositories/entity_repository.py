# Data-access methods for entity repository.
from api import db
from api.models import Entity
from api.models.page_history_model import PageHistory
from api.models.page_model import Page
from api.utils.logging_utils import instrument_repository_class
from sqlalchemy import text


@instrument_repository_class
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
    def create(name: str, type_: str, commit: bool = True) -> Entity:
        entity = Entity(name=name, type=type_)
        db.session.add(entity)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return entity

    @staticmethod
    def update(entity_id: int, commit: bool = True, **kwargs) -> Entity | None:
        entity = Entity.query.get(entity_id)
        if not entity:
            return None
        for key, value in kwargs.items():
            setattr(entity, key, value)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
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
    def _active_without_pages_query():
        """Entities flagged for scraping (to_scrape=True) that have no pages —
        they can never actually be scraped, so they surface as a data anomaly."""
        return (
            Entity.query
            .outerjoin(Page, Page.entity_id == Entity.id)
            .filter(Entity.to_scrape.is_(True))
            .filter(Page.uuid.is_(None))
        )

    @staticmethod
    def get_active_without_pages(limit: int | None = None) -> list[Entity]:
        query = EntityRepository._active_without_pages_query()
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def count_active_without_pages() -> int:
        return EntityRepository._active_without_pages_query().count()

    @staticmethod
    def get_entity_posts_metrics(entity_id: int, date_limit: str=None):
        query = text("""
            SELECT * from page_posts_metrics_mv
            where platform in ('instagram','linkedin','tiktok','youtube','x')
            and entity_id = :entity_id
            and to_scrape
                    """)
        results = db.session.execute(query, {'entity_id': entity_id}).all()
        return results
