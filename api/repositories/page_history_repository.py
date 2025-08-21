from api import db
from api.models import PageHistory
from api.models.page_model import Page
from sqlalchemy import select, and_
from datetime import date, datetime, time

class PageHistoryRepository:
    @staticmethod
    def get_by_id(history_id: int) -> PageHistory | None:
        return PageHistory.query.get(history_id)

    @staticmethod
    def get_all() -> list[PageHistory]:
        return PageHistory.query.all()

    @staticmethod
    def get_today_all() -> list[PageHistory]:
        today = date.today()
        return db.session.scalars(
            select(PageHistory).where(db.func.date(PageHistory.recorded_at) == today)
        ).all()
    
    @staticmethod
    def get_page_data_today(page_id) -> list["PageHistory"]:
        today = date.today()
        return db.session.scalars(
            select(PageHistory).where(
                and_(
                    db.func.date(PageHistory.recorded_at) == today,
                    PageHistory.page_id == page_id
                )
            )
        ).all()
    
    @staticmethod
    def get_entity_data_by_date( entity_id: int, target_date: date):
        stmt = (
            select(PageHistory)
            .join(Page, Page.id == PageHistory.page_id)
            .where(
                and_(
                    Page.entity_id == entity_id,
                    db.func.date(PageHistory.recorded_at) == target_date
                )
            )
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_after_time(hour):
        # Build today 22:00 timestamp
        today = datetime.now().date()
        time_threshold = datetime.combine(today, time(hour, 0))

        stmt = (
            select(PageHistory)
            .where(PageHistory.recorded_at > time_threshold)
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def create(page_id: int, data: dict) -> PageHistory:
        history = PageHistory(page_id=page_id, data=data)
        db.session.add(history)
        db.session.commit()
        return history

    @staticmethod
    def delete(history_id: int) -> bool:
        history = PageHistory.query.get(history_id)
        if not history:
            return False
        db.session.delete(history)
        db.session.commit()
        return True
