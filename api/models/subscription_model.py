from datetime import datetime, timezone

from api import db


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        db.Enum(
            "pending",
            "active",
            "expired",
            "canceled",
            "revoked",
            name="subscription_status",
        ),
        nullable=False,
        default="active",
        index=True,
    )

    pack_code = db.Column(db.String(64), nullable=False)
    access_rights = db.Column(db.JSON, nullable=True)

    starts_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    ends_at = db.Column(db.DateTime, nullable=True, index=True)

    source = db.Column(db.String(50), nullable=False, default="admin")
    preapproved_mail_id = db.Column(
        db.Integer,
        db.ForeignKey("preapproved_mails.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
