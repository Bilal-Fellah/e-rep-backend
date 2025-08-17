from api import db
from api.models import PageHistory

class PageHistoryRepository:
    @staticmethod
    def get_by_id(history_id: int) -> PageHistory | None:
        return PageHistory.query.get(history_id)

    @staticmethod
    def get_all() -> list[PageHistory]:
        return PageHistory.query.all()

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
