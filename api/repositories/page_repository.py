# Data-access methods for page repository.
from api import db
from api.models import Page
from api.utils.logging_utils import instrument_repository_class
from sqlalchemy import func, select


@instrument_repository_class
class PageRepository:
    @staticmethod
    def get_by_id(page_id: int) -> Page | None:
        return Page.query.get(page_id)
    
    @staticmethod
    def get_by_link(page_link: str) -> Page | None:
        return Page.query.filter_by(link=page_link).first()
    
    @staticmethod
    def get_all() -> list[Page]:
        return Page.query.all()

    @staticmethod
    def get_by_platform(query_platform) -> list[Page]:
        return db.session.scalars(
            select(Page).where(Page.platform == query_platform)
        ).all()

    @staticmethod
    def count_by_platform() -> dict[str, int]:
        rows = (
            db.session.query(Page.platform, func.count())
            .group_by(Page.platform)
            .all()
        )
        return {row[0]: row[1] for row in rows}


    @staticmethod
    def create(uuid: str, name: str, link: str, platform: str, entity_id: int, commit: bool = True) -> Page:
        page = Page(uuid= uuid, name=name, link=link, platform=platform, entity_id=entity_id)
        db.session.add(page)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return page

    @staticmethod
    def update(page_id: int, **kwargs) -> Page | None:
        page = Page.query.get(page_id)
        if not page:
            return None
        for key, value in kwargs.items():
            setattr(page, key, value)
        db.session.commit()
        return page

    @staticmethod
    def delete(page_id: int) -> bool:
        page = Page.query.get(page_id)
        if not page:
            return False
        db.session.delete(page)
        db.session.commit()
        return True

    @staticmethod
    def get_active_pages_by_platform(platform: str = None) -> list[Page]:
        """
        Get all pages for active entities (to_scrape=True), optionally filtered by platform.
        
        Args:
            platform: Optional platform filter (instagram, facebook, x, tiktok, linkedin, youtube)
            
        Returns:
            List of Page objects belonging to active entities
        """
        from api.models.entity_model import Entity
        
        query = (
            db.session.query(Page)
            .join(Entity, Page.entity_id == Entity.id)
            .filter(Entity.to_scrape.is_(True))
        )
        
        if platform:
            query = query.filter(Page.platform == platform)
        
        return query.all()
