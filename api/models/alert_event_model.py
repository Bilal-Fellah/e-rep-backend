from datetime import datetime
from sqlalchemy import inspect
from api import db


class AlertEvent(db.Model):
    __tablename__ = "alert_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    dedupe_key = db.Column(db.String(255), nullable=False, unique=True, index=True)

    severity = db.Column(db.String(20), nullable=False, default="warning", index=True)

    entity_id = db.Column(db.Integer, nullable=True, index=True)
    page_id = db.Column(db.String(36), nullable=True, index=True)
    platform = db.Column(db.String(20), nullable=True, index=True)
    post_id = db.Column(db.String(100), nullable=True, index=True)
    comment_pk = db.Column(db.Integer, nullable=True, index=True)

    label = db.Column(db.Integer, nullable=True)
    matched_keyword = db.Column(db.String(255), nullable=True)

    payload = db.Column(db.JSON, nullable=True)
    event_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "event_type IN ('negative_comment', 'keyword_mention', 'engagement_anomaly')",
            name="ck_alert_event_event_type",
        ),
        db.CheckConstraint(
            "severity IN ('info', 'warning', 'serious', 'critical')",
            name="ck_alert_event_severity",
        ),
    )

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
