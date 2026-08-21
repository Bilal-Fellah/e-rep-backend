from datetime import datetime

from api import db
from api.models.alert_detector_checkpoint_model import AlertDetectorCheckpoint
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class AlertDetectorCheckpointRepository:
    @staticmethod
    def get(detector_name: str) -> AlertDetectorCheckpoint | None:
        return AlertDetectorCheckpoint.query.filter_by(detector_name=detector_name).first()

    @staticmethod
    def get_cursor_ts(detector_name: str) -> datetime | None:
        row = AlertDetectorCheckpointRepository.get(detector_name)
        return row.cursor_ts if row else None

    @staticmethod
    def upsert(
        detector_name: str,
        *,
        cursor_ts: datetime | None = None,
        cursor_text: str | None = None,
        meta: dict | None = None,
        commit: bool = True,
    ) -> AlertDetectorCheckpoint:
        row = AlertDetectorCheckpointRepository.get(detector_name)
        if not row:
            row = AlertDetectorCheckpoint()
            row.detector_name = detector_name
            db.session.add(row)

        if cursor_ts is not None:
            row.cursor_ts = cursor_ts
        if cursor_text is not None:
            row.cursor_text = cursor_text
        if meta is not None:
            row.meta = meta
        row.updated_at = datetime.utcnow()

        if commit:
            db.session.commit()
        return row
