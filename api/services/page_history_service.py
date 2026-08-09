# Business workflows for page history monitoring service.
from datetime import datetime
from api.repositories.page_history_repository import PageHistoryRepository
from api.utils.logging_utils import instrument_service_class
from api.utils.request_parsing import parse_iso_date


@instrument_service_class
class PageHistoryService:
    @staticmethod
    def get_filtered_history(
        start_date=None,
        end_date=None,
        brand_id=None,
        brand_name=None,
        platform=None,
        page_id=None,
        search=None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "recorded_at",
        sort_order: str = "desc",
        include_data: bool = True,
    ):
        parsed_start = parse_iso_date(start_date) if start_date else None
        parsed_end = parse_iso_date(end_date) if end_date else None

        if end_date and parsed_end and isinstance(end_date, str) and "T" not in end_date and ":" not in end_date:
            parsed_end = datetime.combine(parsed_end.date(), datetime.max.time())

        if brand_id is not None and not isinstance(brand_id, int):
            try:
                brand_id = int(brand_id)
            except (ValueError, TypeError):
                brand_id = None

        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 20
        elif per_page > 100:
            per_page = 100

        if sort_by not in ("recorded_at", "id"):
            sort_by = "recorded_at"
        if sort_order.lower() not in ("asc", "desc"):
            sort_order = "desc"

        return PageHistoryRepository.get_pages_history_filtered(
            start_date=parsed_start,
            end_date=parsed_end,
            brand_id=brand_id,
            brand_name=brand_name,
            platform=platform,
            page_id=page_id,
            search=search,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            include_data=include_data,
        )

    @staticmethod
    def get_history_by_id(history_id: int):
        if not history_id:
            return None
        return PageHistoryRepository.get_pages_history_by_id(history_id)

    @staticmethod
    def get_filter_options():
        return PageHistoryRepository.get_pages_history_options()

    @staticmethod
    def get_monitoring_summary():
        return PageHistoryRepository.get_pages_history_summary()
