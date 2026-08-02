# Legacy Subscription Backfill Runbook

Use this once after deploying the new subscriptions structure.

Goal: migrate existing users from legacy role-only entitlement into the
new `subscriptions` table so access continues smoothly.

---

## 1) Backup first (required)

### PostgreSQL (recommended)

```bash
pg_dump -Fc -h <HOST> -p <PORT> -U <USER> <DB_NAME> > pre_subscriptions_backfill.dump
```

To restore if needed:

```bash
pg_restore -c -h <HOST> -p <PORT> -U <USER> -d <DB_NAME> pre_subscriptions_backfill.dump
```

---

## 2) Run the backfill in dry-run mode

From project root (with DB env vars loaded: `DB_USER`, `DB_PWD`, `DB_NAME`,
`VPS_ADDRESS`, `VPS_DB_PORT`):

```bash
python scripts/backfill_subscriptions_from_legacy_roles.py
```

Default behavior:
- no writes (dry-run)
- roles = `subscribed`
- pack mapping defaults:
  - subscribed -> `advanced`
  - registered -> `starter`
  - admin -> `advanced`

---

## 3) Apply backfill

```bash
python scripts/backfill_subscriptions_from_legacy_roles.py --apply
```

Optional examples:

```bash
# Put starts_at at user.created_at instead of now
python scripts/backfill_subscriptions_from_legacy_roles.py --apply --start-from-created-at

# Backfill ALL roles with explicit pack mapping
python scripts/backfill_subscriptions_from_legacy_roles.py \
  --roles subscribed,registered,admin \
  --pack-subscribed advanced \
  --pack-registered starter \
  --pack-admin advanced \
  --apply

# Backfill only registered + admin
python scripts/backfill_subscriptions_from_legacy_roles.py \
  --roles registered,admin \
  --pack-registered starter \
  --pack-admin advanced \
  --apply
```

---

## 4) Verify

- `GET /api/admin/users?role=subscribed` should still show expected paid users.
- For sampled users, `GET /api/admin/users/<id>/subscriptions` should show a new
  `source: legacy_role_backfill` row.
- Log in as a migrated user and confirm access works as expected.

---

## Idempotency

The script is idempotent for repeated runs:
- role=subscribed: skips users already covered by any active paid subscription
- role=registered/admin: skips users already covered by an active subscription
  of the target pack

---

## Notes

- `starter` is not allowed for role=`subscribed` mapping (must be paid).
- If you need precise per-customer mapping, run multiple passes or build a
  CSV-driven variant.
