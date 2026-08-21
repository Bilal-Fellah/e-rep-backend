from api import db
from api.models.alert_rule_model import AlertRule
from api.models.alert_rule_keyword_model import AlertRuleKeyword
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class AlertRuleRepository:
    @staticmethod
    def list_for_user(user_id: int, active_only: bool = False) -> list[AlertRule]:
        q = AlertRule.query.filter_by(user_id=user_id)
        if active_only:
            q = q.filter(AlertRule.is_active.is_(True))
        return q.order_by(AlertRule.updated_at.desc(), AlertRule.id.desc()).all()

    @staticmethod
    def get_for_user(rule_id: int, user_id: int) -> AlertRule | None:
        return AlertRule.query.filter_by(id=rule_id, user_id=user_id).first()

    @staticmethod
    def create(data: dict, keywords: list[dict] | None = None, commit: bool = True) -> AlertRule:
        rule = AlertRule(**data)
        db.session.add(rule)
        db.session.flush()

        for kw in keywords or []:
            row = AlertRuleKeyword()
            row.rule_id = rule.id
            row.keyword = kw["keyword"]
            row.keyword_normalized = kw["keyword_normalized"]
            db.session.add(row)

        if commit:
            db.session.commit()
        return rule

    @staticmethod
    def update(rule: AlertRule, fields: dict, keywords: list[dict] | None = None, commit: bool = True) -> AlertRule:
        for key, value in fields.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        if keywords is not None:
            AlertRuleKeyword.query.filter_by(rule_id=rule.id).delete()
            for kw in keywords:
                row = AlertRuleKeyword()
                row.rule_id = rule.id
                row.keyword = kw["keyword"]
                row.keyword_normalized = kw["keyword_normalized"]
                db.session.add(row)

        if commit:
            db.session.commit()
        return rule

    @staticmethod
    def delete(rule: AlertRule, commit: bool = True) -> None:
        db.session.delete(rule)
        if commit:
            db.session.commit()

    @staticmethod
    def list_matching_rules(event_type: str, entity_id: int | None) -> list[AlertRule]:
        q = AlertRule.query.filter(
            AlertRule.is_active.is_(True),
            AlertRule.event_type == event_type,
        )

        if entity_id is None:
            q = q.filter(db.or_(AlertRule.entity_scope.is_(None), AlertRule.entity_scope == {}))
            return q.all()

        rules = q.all()
        matched = []
        for rule in rules:
            scope = rule.entity_scope or {}
            ids = scope.get("entity_ids") if isinstance(scope, dict) else None
            if not ids:
                matched.append(rule)
                continue
            if entity_id in ids:
                matched.append(rule)
        return matched

    @staticmethod
    def list_active_by_event_type(event_type: str) -> list[AlertRule]:
        return AlertRule.query.filter(
            AlertRule.is_active.is_(True),
            AlertRule.event_type == event_type,
        ).all()

    @staticmethod
    def list_keywords_for_rule_ids(rule_ids: list[int]) -> dict[int, list[AlertRuleKeyword]]:
        if not rule_ids:
            return {}
        rows = (
            AlertRuleKeyword.query
            .filter(AlertRuleKeyword.rule_id.in_(rule_ids))
            .order_by(AlertRuleKeyword.id.asc())
            .all()
        )
        out: dict[int, list[AlertRuleKeyword]] = {}
        for row in rows:
            out.setdefault(row.rule_id, []).append(row)
        return out
