# Shared helper functions for period and date resolution.
from datetime import date, datetime, timedelta
from api.utils.request_parsing import parse_iso_date


def resolve_period_dates(period=None, start_date=None, end_date=None):
    """
    Resolves start and end dates based on a predefined period keyword
    or parses explicit start_date and end_date parameters.
    """
    if period:
        normalized = period.strip().lower()
        if normalized == "yesterday":
            start = date.today() - timedelta(days=2)
            end = date.today() - timedelta(days=1)
            return start, end
        elif normalized in ("prev_7d", "previous_7_days", "previous_7d"):
            start = date.today() - timedelta(days=8)
            end = date.today() - timedelta(days=1)
            return start, end
        elif normalized in ("prev_month", "previous_month", "prev_30d", "previous_30d"):
            start = date.today() - timedelta(days=31)
            end = date.today() - timedelta(days=1)
            return start, end
        else:
            raise ValueError(f"Invalid period value: '{period}'. Supported values: yesterday, prev_7d, previous_month.")

    start = parse_iso_date(start_date) if start_date else (datetime.now() - timedelta(days=30)).date()
    end = parse_iso_date(end_date) if end_date else None
    return start, end
