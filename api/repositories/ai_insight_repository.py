from datetime import datetime, timezone
import json
import logging

from api import db
from api.models.ai_insight_cache import AiInsightCache


repository_logger = logging.getLogger("repository_errors")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _log_repository_error(method_name: str, error: Exception, context: dict | None = None) -> None:
    payload = {
        "timestamp": _utc_now_iso(),
        "severity": "high",
        "category": "repository_error",
        "class_name": "ai_insight_repository",
        "method_name": method_name,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {},
    }
    repository_logger.critical(json.dumps(payload, ensure_ascii=True, default=str))


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
    try:
        row = find_by_key(cache_key)

        if row is None:
            row = AiInsightCache()
            row.cache_key = cache_key
            row.view_type = view_type
            row.summary_text = summary_text
            row.model_used = model_used
            row.expires_at = expires_at
            db.session.add(row)
        else:
            row.view_type = view_type
            row.summary_text = summary_text
            row.model_used = model_used
            row.expires_at = expires_at

        db.session.commit()
        return row
    except Exception as error:
        db.session.rollback()
        _log_repository_error(
            "upsert",
            error,
            context={"cache_key": cache_key, "view_type": view_type, "model_used": model_used},
        )
        raise
