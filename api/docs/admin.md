# Admin API

All routes in this document are prefixed with `/api/admin` and require the
`admin` role (JWT via `Authorization: Bearer <token>` or the `access_token`
cookie). They back the standalone Brendex Admin dashboard.

Standard envelope: success → `{ "success": true, "data": ... }`,
error → `{ "success": false, "error": ... }`.

---

## **GET /api/admin/ping**

Lightweight auth/wiring check. Returns the caller's identity.

```json
{ "success": true, "data": { "ok": true, "user_id": 1, "role": "admin" } }
```

---

## **GET /api/admin/users**

List users with optional search and pagination.

### Query Parameters

- `search` (optional) — matches email / first name / last name (case-insensitive)
- `role` (optional) — filter by `registered` | `subscribed` | `admin`
- `limit` (optional, default 50, max 200)
- `offset` (optional, default 0)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "users": [
      {
        "user_id": 1, "first_name": "Jane", "last_name": "Doe",
        "email": "jane@example.com", "role": "admin",
        "profession": "ceo", "phone_number": null,
        "is_verified": true, "created_at": "2026-01-10T09:00:00+00:00",
        "subscription": {
          "pack_code": "growth",
          "status": "active",
          "starts_at": "2026-08-01T00:00:00+00:00",
          "ends_at": "2026-09-01T00:00:00+00:00",
          "access_rights": {
            "top_posts_limit": 3
          }
        }
      }
    ],
    "total": 1, "limit": 50, "offset": 0
  }
}
```

---

## **POST /api/admin/users/<id>/role**

Change a user's role (`registered` | `admin`).

**Important:** The `subscribed` role cannot be set directly via this endpoint.
It is automatically derived from active paid subscriptions. Use
`/api/admin/users/<id>/subscriptions/grant` to grant a subscription pack,
which will sync the user's role to `subscribed`.

Similarly, to remove `subscribed` access, revoke the subscription via
`/api/admin/users/<id>/subscriptions/<subscription_id>/revoke`.

### Request

```json
{ "role": "admin" }
```

### Behavior

- `registered` → `admin`: Promotes user to admin
- `admin` → `registered`: Demotes admin to registered user
- `subscribed` → `registered`: Blocked if user has active paid subscription
- Any role → `subscribed`: Not allowed (use subscription grant instead)

### Errors

- `role must be one of [...]` (400)
- `Cannot directly set role to 'subscribed'...` (400)
- `Cannot downgrade to 'registered': user has an active paid subscription...` (400)
- `You cannot change your own admin role.` (400)
- `User not found.` (404)

---

## **POST /api/admin/users/<id>/activate**

Set a user's account activation flag.

Request: `{ "is_verified": true }` → returns the updated user object.

Errors: `Missing required field: 'is_verified'.` (400), `'is_verified' must be a boolean.` (400), `User not found.` (404).

---

## **GET /api/admin/users/<id>/subscriptions**

List subscription history for a user (newest first).

Query params: `limit` (default 50, max 200), `offset`.

---

## **POST /api/admin/users/<id>/subscriptions/grant**

Grant a subscription pack to a user for a specific window.

### Request

```json
{
  "pack_code": "growth",
  "starts_at": "2026-08-01T00:00:00Z",
  "ends_at": "2026-09-01T00:00:00Z",
  "access_rights": {
    "top_posts_limit": 30,
    "ranking_limit": 30,
    "allow_custom_ranges": false,
    "allow_premium_periods": true
  }
}
```

Notes:
- `starts_at` is optional (defaults to now).
- `ends_at` is optional (no expiry).
- `pack_code` must be one of: `starter`, `growth`, `advanced`.
- `access_rights` is optional; when omitted, defaults are derived from `pack_code`.
- After granting, the user's role is automatically synced to `subscribed` if the pack is paid (`growth` or `advanced`).

---

## **POST /api/admin/users/<user_id>/subscriptions/<subscription_id>/revoke**

Revoke a specific subscription and sync the user's role.

### Behavior

- Marks the subscription as `revoked`
- Automatically syncs the user's role based on remaining active subscriptions
- If no other active paid subscriptions exist, role is downgraded to `registered`

### Request

No body required.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "subscription": {
      "id": 123,
      "status": "revoked",
      "pack_code": "growth",
      "access_rights": { "top_posts_limit": 30, "ranking_limit": 30 },
      "starts_at": "2026-08-01T00:00:00+00:00",
      "ends_at": "2026-09-01T00:00:00+00:00",
      "source": "admin"
    },
    "active_subscription": null,
    "user": {
      "user_id": 1,
      "first_name": "Jane",
      "last_name": "Doe",
      "email": "jane@example.com",
      "role": "registered",
      "profession": "ceo",
      "phone_number": null,
      "is_verified": true,
      "created_at": "2026-01-10T09:00:00+00:00",
      "subscription": null
    }
  }
}
```

If the user has another active subscription after revocation, `active_subscription` will contain its details and the user's role will remain `subscribed`.

### Errors

- `Subscription not found.` (404)
- `Subscription does not belong to this user.` (400)
- `Subscription is already revoked/expired/canceled and cannot be revoked.` (400)

---

## **GET /api/admin/subscriptions**

List all subscriptions with optional filters.

### Query Parameters

- `status` (optional) — filter by `pending` | `active` | `expired` | `canceled` | `revoked`
- `pack_code` (optional) — filter by `starter` | `growth` | `advanced`
- `source` (optional) — filter by `admin` | `preapproved_mail` | `stripe` | `manual`
- `limit` (optional, default 50, max 200)
- `offset` (optional, default 0)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "subscriptions": [
      {
        "id": 123,
        "user_id": 1,
        "status": "active",
        "pack_code": "growth",
        "access_rights": { "top_posts_limit": 30, "ranking_limit": 30 },
        "starts_at": "2026-08-01T00:00:00+00:00",
        "ends_at": "2026-09-01T00:00:00+00:00",
        "source": "admin",
        "preapproved_mail_id": null,
        "created_by_user_id": 2,
        "created_at": "2026-08-01T00:00:00+00:00"
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

### Errors

- `status must be one of [...]` (400)
- `pack_code must be one of [...]` (400)
- `source must be one of [...]` (400)

---

## **GET /api/admin/preapproved-mails**

List preapproved emails.

Query params:
- `email` (contains filter)
- `status` (`pending` | `used` | `revoked` | `expired`)
- `limit` (default 50, max 200), `offset`

---

## **POST /api/admin/preapproved-mails/upsert**

Create or update a preapproved email that will auto-apply during signup.

### Request

```json
{
  "email": "user@example.com",
  "pack_code": "growth",
  "starts_at": "2026-08-01T00:00:00Z",
  "ends_at": "2026-09-01T00:00:00Z",
  "access_rights": {
    "top_posts_limit": 30,
    "ranking_limit": 30,
    "allow_custom_ranges": false,
    "allow_premium_periods": true
  },
  "notes": "Campaign A"
}
```

Notes:
- On successful signup with that email, the row is marked `used` and a
  subscription is created automatically.
- `pack_code` must be one of: `starter`, `growth`, `advanced`.

---

## **POST /api/admin/users/<id>/delete**

Permanently delete a user. An admin cannot delete their own account.

Request: `{}` → `{ "success": true, "data": { "deleted_id": 5 } }`.

Errors: `You cannot delete your own account.` (400), `User not found.` (404).

---

## **GET /api/admin/overview**

Aggregate counts for the dashboard landing (computed in the DB).

```json
{
  "success": true,
  "data": {
    "entities": { "total": 120, "active": 80, "by_type": { "company": 90, "influencer": 25, "small-business": 5 } },
    "pages": { "total": 300, "by_platform": { "instagram": 140, "x": 60, "linkedin": 100 } },
    "users": { "total": 42, "unverified": 3 }
  }
}
```

---

## **GET /api/admin/health**

System health snapshot — DB reachability, scrape freshness, and the recent
high-severity error count. Read-only and best-effort.

```json
{
  "success": true,
  "data": {
    "checked_at": "2026-07-20T10:00:00+00:00",
    "db_ok": true,
    "scraping": {
      "last_session_at": "2026-07-20T04:00:00",
      "last_session_status": "completed",
      "last_success_at": "2026-07-20T04:00:00",
      "stale": false
    },
    "errors": { "high_severity": 0 }
  }
}
```

`scraping.stale` is `true` when the last successful session is older than
`SCRAPE_STALE_HOURS` (26h) or there is none.

---

## **GET /api/admin/alerts**

Aggregated operational alerts, computed on the fly.

```json
{
  "success": true,
  "data": {
    "generated_at": "2026-07-20T10:00:00+00:00",
    "total": 4,
    "summary": { "scraping_failures": 1, "accounts_to_activate": 3, "data_anomalies": 0, "system_errors": 0 },
    "categories": [
      { "key": "scraping_failures", "label": "Scraping failures", "count": 1, "severity": "serious", "items": [ { "session_id": "…", "created_at": "…", "error": "…" } ] }
    ]
  }
}
```

Categories: `scraping_failures`, `accounts_to_activate`, `data_anomalies`, `system_errors`.
Severity per category: `critical` | `serious` | `warning` | `ok`.

---

## **GET /api/admin/logs**

Read the backend JSONL error logs (newest first).

### Query Parameters

- `source` — `route` | `service` | `repository` | `all` (default `all`)
- `severity` — `low` | `medium` | `high` (optional)
- `period` — `YYYY-MM` (default current month)
- `limit` (default 100, max 500), `offset` (default 0)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "logs": [
      { "timestamp": "2026-07-20T09:59:00Z", "severity": "high", "_source": "route",
        "error_type": "SQLAlchemyError", "public_message": "…", "status_code": 500, "stack_trace": "…" }
    ],
    "total": 12, "period": "2026-07", "source": "all",
    "available_periods": ["2026-07", "2026-06"]
  }
}
```

Log reads are scoped to the most recent window per source/month (see
`api/repositories/log_repository.py`).
