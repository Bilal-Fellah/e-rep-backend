import re
from datetime import timedelta, datetime, timezone
from dateutil import parser   # pip install python-dateutil if not already installed

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




def ensure_datetime(value):
    """
    Return a datetime object from either:
      - a datetime instance
      - an ISO8601 string like '2018-02-05T10:39:41.000Z'
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # dateutil handles the Z (UTC) suffix automatically
        return parser.isoparse(value)
    raise TypeError(f"Unsupported date type: {type(value)}")