from datetime import datetime
import re

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
