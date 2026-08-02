#!/usr/bin/env python3
"""
Backfill subscriptions for legacy users by role.

Why:
- Old structure stored entitlement only in users.role.
- New structure stores entitlement in subscriptions (+ access_rights by pack).

Behavior:
- Selects users by chosen roles (subscribed/registered/admin).
- Uses role->pack mapping flags.
- Skips users already covered by an active matching subscription strategy.
- Creates subscriptions for remaining users (idempotent for repeated runs).

Defaults:
- DRY-RUN mode (no DB writes) unless --apply is provided.
- subscribed -> advanced (preserve legacy full subscribed behavior)
- registered -> starter
- admin -> advanced
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api import create_app, db
from api.models.user_model import User
from api.models.subscription_model import Subscription
from api.services.subscription_service import PACK_POLICIES, SubscriptionService

from dotenv import load_dotenv
load_dotenv()  # Reads .env into the environment

def now_utc() -> datetime:
    # Use naive UTC to match Postgres timestamps that may come back naive.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def is_active_subscription(sub: Subscription, now: datetime) -> bool:
    if sub.status != "active":
        return False

    starts_at = _naive_utc(sub.starts_at)
    ends_at = _naive_utc(sub.ends_at)

    if starts_at and starts_at > now:
        return False
    if ends_at and ends_at <= now:
        return False
    return True


def _normalize_pack(pack: str, label: str) -> str:
    normalized = (pack or "").strip().lower()
    if normalized not in PACK_POLICIES:
        raise ValueError(
            f"Unsupported {label} pack '{pack}'. Allowed: {sorted(PACK_POLICIES.keys())}"
        )
    return normalized


def has_active_paid_subscription(user_id: int, now: datetime) -> bool:
    paid_packs = {k for k, v in PACK_POLICIES.items() if bool(v.get("paid"))}
    rows = Subscription.query.filter_by(user_id=user_id).all()
    for row in rows:
        pack = (row.pack_code or "").strip().lower()
        if pack in paid_packs and is_active_subscription(row, now):
            return True
    return False


def has_active_pack_subscription(user_id: int, pack_code: str, now: datetime) -> bool:
    target = (pack_code or "").strip().lower()
    rows = Subscription.query.filter_by(user_id=user_id).all()
    for row in rows:
        pack = (row.pack_code or "").strip().lower()
        if pack == target and is_active_subscription(row, now):
            return True
    return False


def parse_roles_csv(raw: str) -> list[str]:
    allowed = {"subscribed", "registered", "admin"}
    roles = [r.strip().lower() for r in (raw or "").split(",") if r.strip()]
    if not roles:
        raise ValueError("--roles cannot be empty")

    invalid = [r for r in roles if r not in allowed]
    if invalid:
        raise ValueError(f"Unsupported roles {invalid}. Allowed: {sorted(allowed)}")

    # preserve order while deduplicating
    seen = set()
    out = []
    for r in roles:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def run_backfill(
    *,
    roles: list[str],
    pack_for_subscribed: str,
    pack_for_registered: str,
    pack_for_admin: str,
    starts_from_created_at: bool,
    apply: bool,
) -> int:
    now = now_utc()

    role_pack_map = {
        "subscribed": _normalize_pack(pack_for_subscribed, "subscribed"),
        "registered": _normalize_pack(pack_for_registered, "registered"),
        "admin": _normalize_pack(pack_for_admin, "admin"),
    }

    # Guardrail: legacy subscribed users should be migrated to a paid pack.
    if not bool(PACK_POLICIES[role_pack_map["subscribed"]].get("paid")):
        raise ValueError(
            "subscribed users must map to a paid pack (growth or advanced)."
        )

    total_created = 0

    for role in roles:
        target_pack = role_pack_map[role]
        users: list[User] = (
            User.query.filter(User.role == role)
            .order_by(User.id.asc())
            .all()
        )

        print(f"\nRole '{role}': found {len(users)} users. Target pack='{target_pack}'.")

        to_create: list[User] = []
        skipped_existing = 0

        for user in users:
            # subscribed role: skip if already covered by any active PAID pack.
            if role == "subscribed" and has_active_paid_subscription(user.id, now):
                skipped_existing += 1
                continue

            # registered/admin role: skip if active target pack already exists.
            if role in ("registered", "admin") and has_active_pack_subscription(
                user.id, target_pack, now
            ):
                skipped_existing += 1
                continue

            to_create.append(user)

        print(f"Role '{role}': already covered -> {skipped_existing}")
        print(f"Role '{role}': to backfill -> {len(to_create)}")

        if not apply:
            continue

        created = 0
        for user in to_create:
            start_at = user.created_at if starts_from_created_at and user.created_at else now
            if isinstance(start_at, datetime) and start_at.tzinfo is None:
                start_at = start_at.replace(tzinfo=timezone.utc)
            SubscriptionService.grant_subscription(
                user_id=user.id,
                pack_code=target_pack,
                starts_at=start_at,
                ends_at=None,
                access_rights=None,  # derive defaults from pack policy
                source="legacy_role_backfill",
                preapproved_mail_id=None,
                created_by_user_id=None,
            )
            created += 1

        total_created += created
        print(f"Role '{role}': created {created} subscriptions.")

    if not apply:
        print("\nDRY-RUN: no rows were created. Re-run with --apply to write changes.")
        return 0

    # Ensure pending unit-of-work is flushed (grant_subscription already commits per row).
    db.session.commit()

    print(f"\nCreated {total_created} subscription rows in total.")
    print("Backfill complete.")
    return total_created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill subscriptions from legacy users.role")
    parser.add_argument(
        "--roles",
        default="subscribed",
        help="Comma-separated roles to backfill. Allowed: subscribed,registered,admin (default: subscribed)",
    )
    parser.add_argument(
        "--pack-subscribed",
        default="advanced",
        help="Target pack for role=subscribed (default: advanced).",
    )
    parser.add_argument(
        "--pack-registered",
        default="starter",
        help="Target pack for role=registered (default: starter).",
    )
    parser.add_argument(
        "--pack-admin",
        default="advanced",
        help="Target pack for role=admin (default: advanced).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write changes. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--start-from-created-at",
        action="store_true",
        help="Set subscription.starts_at to user.created_at instead of now.",
    )
    return parser.parse_args()


def _validate_required_env() -> None:
    env = (os.getenv("FLASK_ENV") or "development").lower()
    if env == "testing" or os.getenv("TESTING") == "true":
        return

    required = ["DB_USER", "DB_PWD", "DB_NAME", "VPS_ADDRESS", "VPS_DB_PORT"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables for DB connection: "
            + ", ".join(missing)
        )


def main() -> int:
    args = parse_args()

    try:
        _validate_required_env()
        app = create_app()
    except Exception as exc:
        print("Failed to initialize app/database for backfill.")
        print(f"Reason: {exc}")
        print(
            "Tip: export DB_USER, DB_PWD, DB_NAME, VPS_ADDRESS, VPS_DB_PORT "
            "(or run with TESTING=true for local test DB)."
        )
        return 1

    with app.app_context():
        run_backfill(
            roles=parse_roles_csv(args.roles),
            pack_for_subscribed=args.pack_subscribed,
            pack_for_registered=args.pack_registered,
            pack_for_admin=args.pack_admin,
            starts_from_created_at=bool(args.start_from_created_at),
            apply=bool(args.apply),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
