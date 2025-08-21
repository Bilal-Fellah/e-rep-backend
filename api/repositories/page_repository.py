from api import db
from api.models import Page
from sqlalchemy import select


class PageRepository:
    @staticmethod
    def get_by_id(page_id: int) -> Page | None:
        return Page.query.get(page_id)

    @staticmethod
    def get_all() -> list[Page]:
        return Page.query.all()

    @staticmethod
    def get_by_platform(query_platform) -> list[Page]:
        return db.session.scalars(
            select(Page).where(Page.platform == query_platform)
        ).all()


    @staticmethod
    def create(name: str, link: str, platform: str, entity_id: int) -> Page:
        page = Page(name=name, link=link, platform=platform, entity_id=entity_id)
        db.session.add(page)
        db.session.commit()
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
