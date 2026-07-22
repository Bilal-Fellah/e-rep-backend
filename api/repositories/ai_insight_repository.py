from datetime import datetime

from api import db
from api.models.ai_insight_cache import AiInsightCache


def find_by_key(cache_key: str) -> AiInsightCache | None:
    """Return the row for this cache_key, or None."""
    return AiInsightCache.query.filter_by(cache_key=cache_key).first()


def upsert(
    cache_key: str,
    view_type: str,
    summary_text: str,
    model_used: str,
    expires_at: datetime,
) -> AiInsightCache:
    """Insert new row, or update existing row matching cache_key."""
    row = find_by_key(cache_key)

    if row is None:
        row = AiInsightCache(
            cache_key=cache_key,
            view_type=view_type,
            summary_text=summary_text,
            model_used=model_used,
            expires_at=expires_at,
        )
        db.session.add(row)
    else:
        row.view_type = view_type
        row.summary_text = summary_text
        row.model_used = model_used
        row.expires_at = expires_at

    db.session.commit()
    return row
