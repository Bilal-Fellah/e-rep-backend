from datetime import datetime, timezone

from api import db


class PreapprovedMail(db.Model):
    __tablename__ = "preapproved_mails"
    __table_args__ = (
        db.UniqueConstraint("email", name="uq_preapproved_mails_email"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    status = db.Column(
        db.Enum("pending", "used", "revoked", "expired", name="preapproved_mail_status"),
        nullable=False,
        default="pending",
        index=True,
    )
    pack_code = db.Column(db.String(64), nullable=False)
    access_rights = db.Column(db.JSON, nullable=True)

    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)

    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    used_at = db.Column(db.DateTime, nullable=True)
