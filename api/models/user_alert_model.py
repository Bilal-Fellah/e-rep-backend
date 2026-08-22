from datetime import datetime
from sqlalchemy import inspect
from api import db


class UserAlert(db.Model):
    __tablename__ = "user_alerts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey("alert_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id = db.Column(
        db.Integer,
        db.ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = db.Column(db.String(20), nullable=False, default="unread", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    dismissed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('unread', 'read', 'dismissed')",
            name="ck_user_alert_status",
        ),
        db.UniqueConstraint(
            "user_id", "event_id", "rule_id", name="uq_user_alert_user_event_rule"
        ),
    )

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
