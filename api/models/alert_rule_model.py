from datetime import datetime
from sqlalchemy import inspect
from api import db


class AlertRule(db.Model):
    __tablename__ = "alert_rules"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(120), nullable=False)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    severity_min = db.Column(db.String(20), nullable=True)
    entity_scope = db.Column(db.JSON, nullable=True)
    cooldown_minutes = db.Column(db.Integer, nullable=False, default=60)
    match_mode = db.Column(db.String(20), nullable=False, default="contains")
    is_case_sensitive = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.CheckConstraint(
            "event_type IN ('negative_comment', 'keyword_mention', 'engagement_anomaly')",
            name="ck_alert_rule_event_type",
        ),
        db.CheckConstraint(
            "match_mode IN ('contains', 'exact', 'regex')",
            name="ck_alert_rule_match_mode",
        ),
        db.CheckConstraint(
            "cooldown_minutes >= 0",
            name="ck_alert_rule_cooldown_non_negative",
        ),
    )

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
