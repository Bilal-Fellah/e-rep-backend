# Shared helper functions for request parsing.
from datetime import date

from api.utils.posts_utils import ensure_datetime


def parse_iso_date(value):
    if not value:
        return None
    return ensure_datetime(value).date()


def normalize_to_utc_datetime(value):
    if not value:
        return None
    return ensure_datetime(value)


def today_date():
    return date.today()
