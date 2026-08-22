from datetime import datetime
from sqlalchemy import inspect
from api import db


class AlertDetectorCheckpoint(db.Model):
    __tablename__ = "alert_detector_checkpoints"

    detector_name = db.Column(db.String(80), primary_key=True)
    cursor_ts = db.Column(db.DateTime, nullable=True)
    cursor_text = db.Column(db.String(255), nullable=True)
    meta = db.Column(db.JSON, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
