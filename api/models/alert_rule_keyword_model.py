from datetime import datetime
from sqlalchemy import inspect
from api import db


class AlertRuleKeyword(db.Model):
    __tablename__ = "alert_rule_keywords"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rule_id = db.Column(
        db.Integer,
        db.ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword = db.Column(db.String(255), nullable=False)
    keyword_normalized = db.Column(db.String(255), nullable=False, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "rule_id", "keyword_normalized", name="uq_alert_rule_keyword_norm"
        ),
    )

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
