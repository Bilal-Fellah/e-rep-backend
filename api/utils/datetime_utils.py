# Shared datetime serialization helpers.
from datetime import timezone


def iso_utc(dt):
    """Serialize a datetime as an ISO-8601 string carrying a UTC offset.

    Several models store naive-UTC timestamps (e.g. ScrapingSession.created_at
    via datetime.utcnow). Emitting them with bare .isoformat() produces no
    offset, so a browser's `new Date(...)` parses them as *local* time and shows
    the wrong hour. This appends '+00:00' for naive datetimes; aware datetimes
    are returned unchanged. Returns None for None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
