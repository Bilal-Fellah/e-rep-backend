from datetime import datetime, timedelta
import re

from sqlalchemy import String, cast

from api import db
from api.models.comment_model import Comment
from api.models.page_model import Page
from api.models.post_model import PostMV
from api.repositories.alert_event_repository import AlertEventRepository
from api.repositories.alert_rule_repository import AlertRuleRepository
from api.utils.logging_utils import instrument_service_class


ALLOWED_EVENT_TYPES = {"negative_comment", "keyword_mention", "engagement_anomaly"}
ALLOWED_MATCH_MODES = {"contains", "exact", "regex"}


def normalize_keyword(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _is_valid_rule_payload(payload: dict) -> tuple[bool, str | None]:
    if not isinstance(payload, dict):
        return False, "Invalid request payload"

    event_type = (payload.get("event_type") or "").strip()
    if event_type not in ALLOWED_EVENT_TYPES:
        return False, f"event_type must be one of {sorted(ALLOWED_EVENT_TYPES)}"

    name = (payload.get("name") or "").strip()
    if not name:
        return False, "name is required"

    mode = (payload.get("match_mode") or "contains").strip().lower()
    if mode not in ALLOWED_MATCH_MODES:
        return False, f"match_mode must be one of {sorted(ALLOWED_MATCH_MODES)}"

    cooldown_minutes = payload.get("cooldown_minutes", 60)
    try:
        cooldown_minutes = int(cooldown_minutes)
    except (TypeError, ValueError):
        return False, "cooldown_minutes must be an integer"
    if cooldown_minutes < 0:
        return False, "cooldown_minutes must be >= 0"

    scope = payload.get("entity_scope")
    if scope is not None and not isinstance(scope, dict):
        return False, "entity_scope must be an object"

    ids = (scope or {}).get("entity_ids") if isinstance(scope, dict) else None
    if ids is not None:
        if not isinstance(ids, list) or not all(isinstance(x, int) for x in ids):
            return False, "entity_scope.entity_ids must be a list of integers"

    keywords = payload.get("keywords")
    if event_type == "keyword_mention":
        if not isinstance(keywords, list) or not keywords:
            return False, "keywords is required for keyword_mention rules"

    if keywords is not None and not isinstance(keywords, list):
        return False, "keywords must be a list"
    
    # Validate include_historical_events if present
    include_historical = payload.get("include_historical_events")
    if include_historical is not None and not isinstance(include_historical, bool):
        return False, "include_historical_events must be a boolean"

    return True, None


def _normalized_keywords(keywords: list[str] | None) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for raw in keywords or []:
        if not isinstance(raw, str):
            continue
        cleaned = " ".join(raw.strip().split())
        norm = normalize_keyword(cleaned)
        if not cleaned or not norm:
            continue
        if len(norm) < 2:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        out.append({"keyword": cleaned, "keyword_normalized": norm})
    return out


@instrument_service_class
class AlertService:
    @staticmethod
    def _get_env_int(name: str, default: int) -> int:
        import os
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _get_env_str(name: str, default: str) -> str:
        import os
        return os.getenv(name, default)

    @staticmethod
    def _backfill_historical_alerts(
        user_id: int,
        rule_id: int,
        event_type: str,
        entity_scope: dict | None
    ) -> int:
        """
        Create user alerts for historical events that match the rule.
        
        Returns:
            Number of user alerts created
        """
        lookback_days = AlertService._get_env_int("ALERTS_HISTORICAL_BACKFILL_DAYS", 30)
        max_events = AlertService._get_env_int("ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS", 1000)
        
        # Fetch historical events
        events = AlertEventRepository.get_historical_events_for_rule(
            event_type=event_type,
            entity_scope=entity_scope,
            user_id=user_id,
            lookback_days=lookback_days,
            max_events=max_events,
        )
        
        if not events:
            return 0
        
        # Create user alerts for each event
        total_created = 0
        for event in events:
            created = AlertEventRepository.fanout_to_users(
                event_id=event.id,
                rule_ids_by_user={user_id: rule_id},
                commit=False,  # Batch commit at the end
            )
            total_created += created
        
        # Commit all at once
        db.session.commit()

        return total_created

    @staticmethod
    def _scoped_page_ids(entity_scope: dict | None) -> set[str] | None:
        if not isinstance(entity_scope, dict):
            return None

        entity_ids = entity_scope.get("entity_ids")
        if not entity_ids:
            return None

        rows = (
            db.session.query(cast(Page.uuid, String))
            .filter(Page.entity_id.in_(entity_ids))
            .all()
        )
        return {str(row[0]) for row in rows}

    @staticmethod
    def _page_entity_map(page_ids: list[str]) -> dict[str, int]:
        if not page_ids:
            return {}

        rows = (
            db.session.query(cast(Page.uuid, String), Page.entity_id)
            .filter(cast(Page.uuid, String).in_(page_ids))
            .all()
        )
        return {str(page_id): entity_id for page_id, entity_id in rows}

    @staticmethod
    def _backfill_historical_keyword_alerts(
        user_id: int,
        rule_id: int,
        *,
        keywords: list[dict[str, str]],
        match_mode: str,
        is_case_sensitive: bool,
        entity_scope: dict | None,
    ) -> int:
        if not keywords:
            return 0

        lookback_days = AlertService._get_env_int("ALERTS_HISTORICAL_BACKFILL_DAYS", 30)
        max_events = AlertService._get_env_int("ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS", 1000)
        max_scan = max(max_events * 20, max_events)
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)

        scoped_page_ids = AlertService._scoped_page_ids(entity_scope)
        if scoped_page_ids is not None and not scoped_page_ids:
            return 0

        total_created = 0

        comments_q = Comment.query.filter(Comment.recorded_at >= cutoff)
        if scoped_page_ids is not None:
            comments_q = comments_q.filter(Comment.page_id.in_(list(scoped_page_ids)))
        comments = comments_q.order_by(Comment.recorded_at.desc()).limit(max_scan).all()

        comment_page_map = AlertService._page_entity_map(list({str(c.page_id) for c in comments}))

        for row in comments:
            if total_created >= max_events:
                break

            source_text = row.text or ""
            if not source_text:
                continue
            source_norm = normalize_keyword(source_text)
            entity_id = comment_page_map.get(str(row.page_id))

            for kw in keywords:
                if total_created >= max_events:
                    break

                if not AlertService.match_keyword(
                    text_original=source_text,
                    text_normalized=source_norm,
                    keyword_original=kw["keyword"],
                    keyword_normalized=kw["keyword_normalized"],
                    match_mode=match_mode,
                    is_case_sensitive=is_case_sensitive,
                ):
                    continue

                event_data = {
                    "event_type": "keyword_mention",
                    "dedupe_key": f"kw:c:{row.id}:{kw['keyword_normalized']}",
                    "severity": "warning",
                    "entity_id": entity_id,
                    "page_id": str(row.page_id),
                    "platform": row.platform,
                    "post_id": row.post_id,
                    "comment_pk": row.id,
                    "matched_keyword": kw["keyword"],
                    "payload": {
                        "source": "comment",
                        "text": row.text,
                        "keyword_normalized": kw["keyword_normalized"],
                        "rule_id": rule_id,
                        "historical_backfill": True,
                    },
                    "event_at": row.recorded_at,
                }

                event, _ = AlertEventRepository.create_or_get(event_data)
                total_created += AlertEventRepository.fanout_to_users(
                    event.id,
                    {user_id: rule_id},
                    commit=True,
                )

        if total_created >= max_events:
            return total_created

        posts_q = PostMV.query.filter(
            PostMV.recorded_at >= cutoff,
            PostMV.caption.isnot(None),
            PostMV.caption != "",
        )
        if scoped_page_ids is not None:
            posts_q = posts_q.filter(PostMV.page_id.in_(list(scoped_page_ids)))
        posts = posts_q.order_by(PostMV.recorded_at.desc()).limit(max_scan).all()

        post_page_map = AlertService._page_entity_map(list({str(p.page_id) for p in posts}))

        for row in posts:
            if total_created >= max_events:
                break

            source_text = row.caption or ""
            source_norm = normalize_keyword(source_text)
            entity_id = post_page_map.get(str(row.page_id))

            for kw in keywords:
                if total_created >= max_events:
                    break

                if not AlertService.match_keyword(
                    text_original=source_text,
                    text_normalized=source_norm,
                    keyword_original=kw["keyword"],
                    keyword_normalized=kw["keyword_normalized"],
                    match_mode=match_mode,
                    is_case_sensitive=is_case_sensitive,
                ):
                    continue

                event_data = {
                    "event_type": "keyword_mention",
                    "dedupe_key": (
                        f"kw:p:{row.page_id}:{row.platform}:{row.post_id}:{kw['keyword_normalized']}"
                    ),
                    "severity": "warning",
                    "entity_id": entity_id,
                    "page_id": str(row.page_id),
                    "platform": row.platform,
                    "post_id": row.post_id,
                    "matched_keyword": kw["keyword"],
                    "payload": {
                        "source": "post",
                        "text": row.caption,
                        "keyword_normalized": kw["keyword_normalized"],
                        "rule_id": rule_id,
                        "historical_backfill": True,
                    },
                    "event_at": row.recorded_at or row.created_at or datetime.utcnow(),
                }

                event, _ = AlertEventRepository.create_or_get(event_data)
                total_created += AlertEventRepository.fanout_to_users(
                    event.id,
                    {user_id: rule_id},
                    commit=True,
                )

        return total_created

    @staticmethod
    def list_rules(user_id: int) -> list[dict]:
        rules = AlertRuleRepository.list_for_user(user_id)
        ids = [r.id for r in rules]
        kw_map = AlertRuleRepository.list_keywords_for_rule_ids(ids)

        data = []
        for rule in rules:
            item = rule.to_dict()
            item["keywords"] = [k.keyword for k in kw_map.get(rule.id, [])]
            data.append(item)
        return data

    @staticmethod
    def create_rule(user_id: int, payload: dict):
        ok, err = _is_valid_rule_payload(payload)
        if not ok:
            raise ValueError(err)

        event_type = payload["event_type"].strip()
        keywords = _normalized_keywords(payload.get("keywords"))
        if event_type == "keyword_mention" and not keywords:
            raise ValueError("keywords is required for keyword_mention rules")

        data = {
            "user_id": user_id,
            "name": payload["name"].strip(),
            "event_type": event_type,
            "is_active": bool(payload.get("is_active", True)),
            "severity_min": payload.get("severity_min"),
            "entity_scope": payload.get("entity_scope") or None,
            "cooldown_minutes": int(payload.get("cooldown_minutes", 60)),
            "match_mode": (payload.get("match_mode") or "contains").strip().lower(),
            "is_case_sensitive": bool(payload.get("is_case_sensitive", False)),
        }
        rule = AlertRuleRepository.create(data, keywords=keywords)

        created = rule.to_dict()
        created["keywords"] = [k["keyword"] for k in keywords]
        
        # Handle historical backfill if requested
        include_historical = bool(payload.get("include_historical_events", False))
        historical_alerts_created = 0
        
        if include_historical:
            backfill_mode = AlertService._get_env_str("ALERTS_HISTORICAL_BACKFILL_MODE", "sync")

            if backfill_mode == "async":
                # TODO: Implement async backfill using background job queue
                # For now, fall back to sync
                pass

            if event_type == "keyword_mention":
                historical_alerts_created = AlertService._backfill_historical_keyword_alerts(
                    user_id=user_id,
                    rule_id=rule.id,
                    keywords=keywords,
                    match_mode=str(data["match_mode"]),
                    is_case_sensitive=bool(data["is_case_sensitive"]),
                    entity_scope=data["entity_scope"] if isinstance(data["entity_scope"], dict) else None,
                )
            else:
                historical_alerts_created = AlertService._backfill_historical_alerts(
                    user_id=user_id,
                    rule_id=rule.id,
                    event_type=event_type,
                    entity_scope=data["entity_scope"] if isinstance(data["entity_scope"], dict) else None,
                )
        
        created["historical_alerts_created"] = historical_alerts_created
        return created

    @staticmethod
    def update_rule(user_id: int, rule_id: int, payload: dict):
        rule = AlertRuleRepository.get_for_user(rule_id, user_id)
        if not rule:
            return None

        merged = rule.to_dict()
        merged.update(payload or {})
        ok, err = _is_valid_rule_payload(merged)
        if not ok:
            raise ValueError(err)

        fields = {
            "name": merged["name"].strip(),
            "event_type": merged["event_type"].strip(),
            "is_active": bool(merged.get("is_active", True)),
            "severity_min": merged.get("severity_min"),
            "entity_scope": merged.get("entity_scope") or None,
            "cooldown_minutes": int(merged.get("cooldown_minutes", 60)),
            "match_mode": (merged.get("match_mode") or "contains").strip().lower(),
            "is_case_sensitive": bool(merged.get("is_case_sensitive", False)),
            "updated_at": datetime.utcnow(),
        }

        keywords_payload = payload.get("keywords") if isinstance(payload, dict) and "keywords" in payload else None
        keywords = _normalized_keywords(keywords_payload) if keywords_payload is not None else None

        if fields["event_type"] == "keyword_mention":
            if keywords is None:
                existing_map = AlertRuleRepository.list_keywords_for_rule_ids([rule.id])
                existing = existing_map.get(rule.id, [])
                if not existing:
                    raise ValueError("keywords is required for keyword_mention rules")
            elif not keywords:
                raise ValueError("keywords is required for keyword_mention rules")

        updated = AlertRuleRepository.update(rule, fields, keywords=keywords)
        kw_map = AlertRuleRepository.list_keywords_for_rule_ids([updated.id])
        out = updated.to_dict()
        out["keywords"] = [k.keyword for k in kw_map.get(updated.id, [])]

        include_historical = bool(payload.get("include_historical_events", False))
        historical_alerts_created = 0

        if include_historical:
            if fields["event_type"] == "keyword_mention":
                effective_keywords = [
                    {"keyword": str(k.keyword), "keyword_normalized": str(k.keyword_normalized)}
                    for k in kw_map.get(updated.id, [])
                ]
                historical_alerts_created = AlertService._backfill_historical_keyword_alerts(
                    user_id=user_id,
                    rule_id=updated.id,
                    keywords=effective_keywords,
                    match_mode=str(fields["match_mode"]),
                    is_case_sensitive=bool(fields["is_case_sensitive"]),
                    entity_scope=fields["entity_scope"] if isinstance(fields["entity_scope"], dict) else None,
                )
            else:
                historical_alerts_created = AlertService._backfill_historical_alerts(
                    user_id=user_id,
                    rule_id=updated.id,
                    event_type=str(fields["event_type"]),
                    entity_scope=fields["entity_scope"] if isinstance(fields["entity_scope"], dict) else None,
                )

        out["historical_alerts_created"] = historical_alerts_created
        return out

    @staticmethod
    def delete_rule(user_id: int, rule_id: int) -> bool:
        rule = AlertRuleRepository.get_for_user(rule_id, user_id)
        if not rule:
            return False
        AlertRuleRepository.delete(rule)
        return True

    @staticmethod
    def list_alerts(user_id: int, status: str | None, event_type: str | None, limit: int, offset: int):
        rows = AlertEventRepository.list_user_alerts(
            user_id,
            status=status,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
        result = []
        for row in rows:
            ua, event = row[0], row[1]
            result.append(
                {
                    "user_alert_id": ua.id,
                    "status": ua.status,
                    "created_at": ua.created_at.isoformat() if ua.created_at else None,
                    "read_at": ua.read_at.isoformat() if ua.read_at else None,
                    "dismissed_at": ua.dismissed_at.isoformat() if ua.dismissed_at else None,
                    "event": {
                        "id": event.id,
                        "event_type": event.event_type,
                        "severity": event.severity,
                        "event_at": event.event_at.isoformat() if event.event_at else None,
                        "entity_id": event.entity_id,
                        "page_id": event.page_id,
                        "platform": event.platform,
                        "post_id": event.post_id,
                        "comment_pk": event.comment_pk,
                        "label": event.label,
                        "matched_keyword": event.matched_keyword,
                        "payload": event.payload,
                    },
                }
            )
        return result

    @staticmethod
    def unread_count(user_id: int) -> int:
        return AlertEventRepository.count_user_unread(user_id)

    @staticmethod
    def mark_read(user_id: int, user_alert_id: int) -> bool:
        row = AlertEventRepository.get_user_alert(user_alert_id, user_id)
        if not row:
            return False
        AlertEventRepository.mark_read(row)
        return True

    @staticmethod
    def mark_dismissed(user_id: int, user_alert_id: int) -> bool:
        row = AlertEventRepository.get_user_alert(user_alert_id, user_id)
        if not row:
            return False
        AlertEventRepository.mark_dismissed(row)
        return True

    @staticmethod
    def mark_all_read(user_id: int) -> int:
        return AlertEventRepository.mark_all_read(user_id)

    @staticmethod
    def _regex_matches(pattern: str, text: str, case_sensitive: bool = False) -> bool:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            return re.search(pattern, text, flags=flags) is not None
        except re.error:
            return False

    @staticmethod
    def match_keyword(
        *,
        text_original: str,
        text_normalized: str,
        keyword_original: str,
        keyword_normalized: str,
        match_mode: str,
        is_case_sensitive: bool,
    ) -> bool:
        source = text_original or ""
        if not source:
            return False

        if match_mode == "regex":
            return AlertService._regex_matches(
                keyword_original,
                source,
                case_sensitive=is_case_sensitive,
            )

        if is_case_sensitive:
            haystack = " ".join(source.strip().split())
            needle = " ".join((keyword_original or "").strip().split())
        else:
            haystack = text_normalized
            needle = keyword_normalized

        if not haystack or not needle:
            return False

        if match_mode == "exact":
            return haystack == needle

        # default: contains
        return needle in haystack
