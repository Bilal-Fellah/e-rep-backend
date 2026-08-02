from datetime import datetime, timezone

from api import db
from api.models.preapproved_mail_model import PreapprovedMail
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class PreapprovedMailRepository:
    @staticmethod
    def get_by_email(email: str) -> PreapprovedMail | None:
        normalized = (email or "").strip().lower()
        if not normalized:
            return None
        return PreapprovedMail.query.filter_by(email=normalized).first()

    @staticmethod
    def upsert(
        *,
        email: str,
        pack_code: str,
        access_rights: dict | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        notes: str | None = None,
        created_by_user_id: int | None = None,
    ) -> PreapprovedMail:
        normalized = (email or "").strip().lower()
        if not normalized:
            raise ValueError("email is required")

        row = PreapprovedMailRepository.get_by_email(normalized)
        if not row:
            row = PreapprovedMail()
            row.email = normalized
            db.session.add(row)

        row.pack_code = str(pack_code).strip()
        row.access_rights = access_rights
        row.starts_at = starts_at
        row.ends_at = ends_at
        row.notes = notes
        row.created_by_user_id = created_by_user_id
        row.status = "pending"
        row.used_at = None

        db.session.commit()
        return row

    @staticmethod
    def get_eligible_by_email(email: str, now: datetime | None = None) -> PreapprovedMail | None:
        normalized = (email or "").strip().lower()
        if not normalized:
            return None

        now = now or datetime.now(timezone.utc)
        return (
            PreapprovedMail.query.filter(
                PreapprovedMail.email == normalized,
                PreapprovedMail.status == "pending",
                db.or_(PreapprovedMail.starts_at.is_(None), PreapprovedMail.starts_at <= now),
                db.or_(PreapprovedMail.ends_at.is_(None), PreapprovedMail.ends_at >= now),
            )
            .order_by(PreapprovedMail.id.desc())
            .first()
        )

    @staticmethod
    def mark_used(preapproved_id: int, used_at: datetime | None = None) -> PreapprovedMail:
        row = db.session.get(PreapprovedMail, preapproved_id)
        if not row:
            raise ValueError("Preapproved email not found")

        row.status = "used"
        row.used_at = used_at or datetime.now(timezone.utc)
        db.session.commit()
        return row

    @staticmethod
    def list_items(
        *,
        email: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PreapprovedMail]:
        query = PreapprovedMail.query

        if email:
            like = f"%{email.strip().lower()}%"
            query = query.filter(db.func.lower(PreapprovedMail.email).like(like))

        if status:
            query = query.filter(PreapprovedMail.status == status)

        return (
            query.order_by(PreapprovedMail.created_at.desc().nullslast(), PreapprovedMail.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @staticmethod
    def count_items(*, email: str | None = None, status: str | None = None) -> int:
        query = PreapprovedMail.query

        if email:
            like = f"%{email.strip().lower()}%"
            query = query.filter(db.func.lower(PreapprovedMail.email).like(like))

        if status:
            query = query.filter(PreapprovedMail.status == status)

        return query.count()
