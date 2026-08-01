from datetime import datetime, timezone

from api import db
from api.models.subscription_model import Subscription
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class SubscriptionRepository:
    @staticmethod
    def create(
        *,
        user_id: int,
        pack_code: str,
        starts_at: datetime,
        ends_at: datetime | None,
        access_rights: dict | None = None,
        status: str = "active",
        source: str = "admin",
        preapproved_mail_id: int | None = None,
        created_by_user_id: int | None = None,
    ) -> Subscription:
        row = Subscription()
        row.user_id = user_id
        row.pack_code = pack_code
        row.starts_at = starts_at
        row.ends_at = ends_at
        row.access_rights = access_rights
        row.status = status
        row.source = source
        row.preapproved_mail_id = preapproved_mail_id
        row.created_by_user_id = created_by_user_id
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def get_active_for_user(user_id: int, now: datetime | None = None) -> Subscription | None:
        now = now or datetime.now(timezone.utc)
        return (
            Subscription.query.filter(
                Subscription.user_id == user_id,
                Subscription.status == "active",
                Subscription.starts_at <= now,
                db.or_(Subscription.ends_at.is_(None), Subscription.ends_at > now),
            )
            .order_by(Subscription.starts_at.desc(), Subscription.id.desc())
            .first()
        )

    @staticmethod
    def list_for_user(user_id: int, limit: int = 50, offset: int = 0) -> list[Subscription]:
        return (
            Subscription.query.filter_by(user_id=user_id)
            .order_by(Subscription.created_at.desc().nullslast(), Subscription.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @staticmethod
    def expire_due(now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        updated = (
            Subscription.query.filter(
                Subscription.status == "active",
                Subscription.ends_at.isnot(None),
                Subscription.ends_at <= now,
            )
            .update({"status": "expired"}, synchronize_session=False)
        )
        db.session.commit()
        return int(updated or 0)

    @staticmethod
    def revoke(subscription_id: int) -> Subscription | None:
        """Mark a subscription as revoked. Returns the updated subscription or None if not found."""
        sub = Subscription.query.get(subscription_id)
        if not sub:
            return None
        if sub.status in ("revoked", "expired", "canceled"):
            return sub  # Already in a terminal state
        sub.status = "revoked"
        db.session.commit()
        return sub

    @staticmethod
    def get_by_id(subscription_id: int) -> Subscription | None:
        return Subscription.query.get(subscription_id)

    @staticmethod
    def list_all(
        status: str | None = None,
        pack_code: str | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Subscription]:
        """List all subscriptions with optional filters."""
        query = Subscription.query

        if status:
            query = query.filter(Subscription.status == status)
        if pack_code:
            query = query.filter(Subscription.pack_code == pack_code)
        if source:
            query = query.filter(Subscription.source == source)

        return (
            query.order_by(Subscription.created_at.desc().nullslast(), Subscription.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @staticmethod
    def count_all(
        status: str | None = None,
        pack_code: str | None = None,
        source: str | None = None,
    ) -> int:
        """Count all subscriptions with optional filters."""
        query = Subscription.query

        if status:
            query = query.filter(Subscription.status == status)
        if pack_code:
            query = query.filter(Subscription.pack_code == pack_code)
        if source:
            query = query.filter(Subscription.source == source)

        return query.count()
