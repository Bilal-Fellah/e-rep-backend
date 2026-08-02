from datetime import datetime, timezone

from api import db
from api.models.subscription_model import Subscription
from api.repositories.preapproved_mail_repository import PreapprovedMailRepository
from api.repositories.subscription_repository import SubscriptionRepository
from api.repositories.user_repository import UserRepository
from api.utils.logging_utils import instrument_service_class


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_datetime(value, field_name: str):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        raise ValueError(f"{field_name} must be an ISO datetime string.")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


PACK_POLICIES = {
    "starter": {
        "paid": False,
        "priority": 0,
        "default_access_rights": {
            "ranking_limit": 10,
            "top_posts_limit": 1,
            "allow_custom_ranges": False,
            "allow_premium_periods": False,
            "category_scope": "single",
        },
    },
    "growth": {
        "paid": True,
        "priority": 10,
        "default_access_rights": {
            "ranking_limit": 30,
            "top_posts_limit": 30,
            "allow_custom_ranges": False,
            "allow_premium_periods": True,
            "category_scope": "single",
        },
    },
    "advanced": {
        "paid": True,
        "priority": 20,
        "default_access_rights": {
            "ranking_limit": 50,
            "top_posts_limit": 50,
            "allow_custom_ranges": True,
            "allow_premium_periods": True,
            "category_scope": "all",
            "ai_insights": True,
            "ai_recommendations": True,
            "comment_sentiment": True,
            "influencer_discovery": True,
            "ereputation_score": True,
        },
    },
}


@instrument_service_class
class SubscriptionService:
    @staticmethod
    def parse_window(starts_at, ends_at):
        starts = _parse_iso_datetime(starts_at, "starts_at")
        ends = _parse_iso_datetime(ends_at, "ends_at")

        if starts is None:
            starts = _now_utc()

        if ends is not None and ends <= starts:
            raise ValueError("ends_at must be greater than starts_at")

        return starts, ends

    @staticmethod
    def _subscription_status_for_window(starts_at: datetime, ends_at: datetime | None):
        now = _now_utc()
        if ends_at is not None and ends_at <= now:
            return "expired"
        if starts_at > now:
            return "pending"
        return "active"

    @staticmethod
    def _normalize_pack_code(pack_code: str) -> str:
        normalized = (pack_code or "").strip().lower()
        if normalized not in PACK_POLICIES:
            raise ValueError(
                f"Unsupported pack_code '{pack_code}'. Allowed: {sorted(PACK_POLICIES.keys())}"
            )
        return normalized

    @staticmethod
    def _effective_access_rights(pack_code: str, access_rights: dict | None):
        policy = PACK_POLICIES[pack_code]
        defaults = dict(policy.get("default_access_rights") or {})
        custom = access_rights if isinstance(access_rights, dict) else {}
        defaults.update(custom)
        return defaults

    @staticmethod
    def _is_paid_pack(pack_code: str) -> bool:
        return bool(PACK_POLICIES.get(pack_code, {}).get("paid", False))

    @staticmethod
    def _pack_priority(pack_code: str) -> int:
        return int(PACK_POLICIES.get(pack_code, {}).get("priority", -1))

    @staticmethod
    def _select_effective_active_subscription(user_id: int):
        now = _now_utc()
        rows = (
            Subscription.query.filter(
                Subscription.user_id == user_id,
                Subscription.status == "active",
                Subscription.starts_at <= now,
                db.or_(Subscription.ends_at.is_(None), Subscription.ends_at > now),
            )
            .all()
        )
        if not rows:
            return None

        rows.sort(
            key=lambda s: (
                SubscriptionService._is_paid_pack((s.pack_code or "").strip().lower()),
                SubscriptionService._pack_priority((s.pack_code or "").strip().lower()),
                s.starts_at or datetime.min.replace(tzinfo=timezone.utc),
                s.id or 0,
            ),
            reverse=True,
        )
        return rows[0]

    @staticmethod
    def _sync_user_role_from_subscriptions(user_id: int):
        user = UserRepository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Keep the subscriptions table clean by expiring old active rows first.
        SubscriptionRepository.expire_due()
        active = SubscriptionService._select_effective_active_subscription(user.id)

        if user.role == "admin":
            return user, active

        active_pack = (getattr(active, "pack_code", "") or "").strip().lower()
        desired_role = "subscribed" if (active and SubscriptionService._is_paid_pack(active_pack)) else "registered"
        if user.role != desired_role:
            user = UserRepository.update_profile(user.id, role=desired_role)

        return user, active

    @staticmethod
    def grant_subscription(
        *,
        user_id: int,
        pack_code: str,
        starts_at,
        ends_at,
        access_rights: dict | None = None,
        source: str = "admin",
        preapproved_mail_id: int | None = None,
        created_by_user_id: int | None = None,
    ):
        if not pack_code or not str(pack_code).strip():
            raise ValueError("pack_code is required")

        normalized_pack = SubscriptionService._normalize_pack_code(str(pack_code))
        merged_rights = SubscriptionService._effective_access_rights(
            normalized_pack, access_rights
        )

        starts, ends = SubscriptionService.parse_window(starts_at, ends_at)
        status = SubscriptionService._subscription_status_for_window(starts, ends)

        created = SubscriptionRepository.create(
            user_id=user_id,
            pack_code=normalized_pack,
            starts_at=starts,
            ends_at=ends,
            access_rights=merged_rights,
            status=status,
            source=source,
            preapproved_mail_id=preapproved_mail_id,
            created_by_user_id=created_by_user_id,
        )

        user, active = SubscriptionService._sync_user_role_from_subscriptions(user_id)
        return created, user, active

    @staticmethod
    def upsert_preapproved_mail(
        *,
        email: str,
        pack_code: str,
        starts_at,
        ends_at,
        access_rights: dict | None = None,
        notes: str | None = None,
        created_by_user_id: int | None = None,
    ):
        normalized_pack = SubscriptionService._normalize_pack_code(str(pack_code))
        merged_rights = SubscriptionService._effective_access_rights(
            normalized_pack, access_rights
        )

        starts, ends = SubscriptionService.parse_window(starts_at, ends_at)

        return PreapprovedMailRepository.upsert(
            email=email,
            pack_code=normalized_pack,
            starts_at=starts,
            ends_at=ends,
            access_rights=merged_rights,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )

    @staticmethod
    def apply_preapproved_subscription_for_user(user):
        if not user:
            return None, None

        email = getattr(user, "email", None)
        user_id = getattr(user, "id", None)
        if not email:
            return None, None

        preapproved = PreapprovedMailRepository.get_eligible_by_email(email)
        if not preapproved:
            # Even when no preapproval exists, keep role aligned with current active subs
            # only when the user is persisted.
            if isinstance(user_id, int):
                _, active = SubscriptionService._sync_user_role_from_subscriptions(user_id)
                return None, active
            return None, None

        if not isinstance(user_id, int):
            return None, None

        created, _, active = SubscriptionService.grant_subscription(
            user_id=user_id,
            pack_code=preapproved.pack_code,
            starts_at=preapproved.starts_at,
            ends_at=preapproved.ends_at,
            access_rights=preapproved.access_rights,
            source="preapproved_mail",
            preapproved_mail_id=preapproved.id,
            created_by_user_id=preapproved.created_by_user_id,
        )
        PreapprovedMailRepository.mark_used(preapproved.id)
        return created, active

    @staticmethod
    def get_effective_access(user_id: int):
        user, active = SubscriptionService._sync_user_role_from_subscriptions(user_id)
        rights = active.access_rights if active else None
        return user, active, rights

    @staticmethod
    def get_effective_access_for_user(user):
        """Best-effort effective access resolver that tolerates mocked/transient users."""
        if not user:
            return None, None, None

        user_id = getattr(user, "id", None)
        if not isinstance(user_id, int):
            return user, None, None

        persisted = UserRepository.get_by_id(user_id)
        if not persisted:
            return user, None, None

        return SubscriptionService.get_effective_access(user_id)

    @staticmethod
    def revoke_subscription(subscription_id: int):
        """Revoke a subscription and sync the user's role.

        Returns:
            tuple: (revoked_subscription, synced_user, active_subscription_after_revoke)
            Raises:
            ValueError: If subscription not found
        """
        sub = SubscriptionRepository.get_by_id(subscription_id)
        if not sub:
            raise ValueError("Subscription not found")

        # Mark as revoked
        revoked = SubscriptionRepository.revoke(subscription_id)
        if not revoked:
            raise ValueError("Failed to revoke subscription")

        # Sync the user's role based on remaining active subscriptions
        user, active = SubscriptionService._sync_user_role_from_subscriptions(sub.user_id)

        return revoked, user, active
