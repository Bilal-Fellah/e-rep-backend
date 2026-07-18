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
        today = date.today()
        yesterday = today - timedelta(days=1)

        # "All time" — a start_date far enough back to cover all ingested data,
        # no upper bound.
        if normalized in ("all", "all_time", "max"):
            return date(2015, 1, 1), None
        if normalized == "yesterday":
            return today - timedelta(days=2), yesterday
        if normalized in ("7d", "last_7d", "prev_7d", "previous_7_days", "previous_7d"):
            return today - timedelta(days=8), yesterday
        if normalized in ("30d", "last_30d", "last_month"):
            return today - timedelta(days=31), yesterday
        if normalized in ("prev_month", "previous_month", "prev_30d", "previous_30d"):
            return today - timedelta(days=60), today - timedelta(days=30)
        if normalized in ("90d", "last_90d"):
            return today - timedelta(days=91), yesterday
        if normalized in ("1y", "last_year", "365d"):
            return today - timedelta(days=366), yesterday
        raise ValueError(
            f"Invalid period value: '{period}'. Supported values: all, yesterday, "
            "7d, 30d, prev_month, 90d, 1y."
        )

    start = parse_iso_date(start_date) if start_date else (datetime.now() - timedelta(days=30)).date()
    end = parse_iso_date(end_date) if end_date else None
    return start, end
