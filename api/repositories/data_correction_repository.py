# Data-access methods for the data corrections audit log.
from api import db
from api.models import DataCorrection
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class DataCorrectionRepository:
    @staticmethod
    def create(
        target_type: str,
        target_id: str,
        field: str,
        old_value: str | None,
        new_value: str | None,
        reason: str,
        admin_user_id: int | None,
        commit: bool = True,
    ) -> DataCorrection:
        row = DataCorrection(
            target_type=target_type,
            target_id=str(target_id),
            field=field,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            admin_user_id=admin_user_id,
        )
        db.session.add(row)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return row

    @staticmethod
    def list_all(target_type: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[DataCorrection], int]:
        query = DataCorrection.query
        if target_type:
            query = query.filter_by(target_type=target_type)
        total = query.count()
        rows = (
            query.order_by(DataCorrection.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return rows, total
