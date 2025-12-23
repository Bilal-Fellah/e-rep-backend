import re
from datetime import timedelta, datetime, timezone
from dateutil import parser   # pip install python-dateutil if not already installed
import pytz
from sqlalchemy import func, literal

def parse_relative_time(text):
    # Simple pattern matching
    match = re.match(r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago", text)
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    now = datetime.now(timezone.utc)

    # Map units to timedelta
    factors = {
        "minute": timedelta(minutes=value),
        "hour":   timedelta(hours=value),
        "day":    timedelta(days=value),
        "week":   timedelta(weeks=value),
        "month":  timedelta(days=30*value),   # rough month
        "year":   timedelta(days=365*value),  # rough year
    }
    return now - factors[unit]

def _to_number(x):
    """Try to coerce metric values to int safely, fallback to 0."""
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return 0


def ensure_datetime(value):
    """
    Converts a datetime or string into a timezone-aware UTC datetime.
    Supports:
      - naive datetime
      - aware datetime
      - ISO8601 strings (e.g., '2018-02-05T10:39:41.000Z')
    """

    # If already datetime
    if isinstance(value, datetime):
        # If naive → localize to UTC
        if value.tzinfo is None:
            return pytz.UTC.localize(value)
        # If aware → convert to UTC
        return value.astimezone(pytz.UTC)

    # If string → parse then convert
    if isinstance(value, str):
        dt = parser.isoparse(value)
        if dt.tzinfo is None:
            return pytz.UTC.localize(dt)
        return dt.astimezone(pytz.UTC)

    raise TypeError(f"Unsupported date type: {type(value)}")



def jsonb_projection(post_col, fields):
    args = []
    for f in fields:
        args.extend([
            literal(f),
            func.jsonb_extract_path(post_col, f)
        ])
    return func.jsonb_build_object(*args)


from sqlalchemy import func, literal

def jsonb_projection_from_alias(post_alias, fields):
    args = []
    for f in fields:
        args.extend([
            literal(f),
            func.jsonb_extract_path(post_alias.c.value, f)
        ])
    return func.jsonb_build_object(*args)
