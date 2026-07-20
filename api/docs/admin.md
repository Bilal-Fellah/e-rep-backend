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
        "is_verified": true, "created_at": "2026-01-10T09:00:00+00:00"
      }
    ],
    "total": 1, "limit": 50, "offset": 0
  }
}
```

---

## **POST /api/admin/users/&lt;id&gt;/role**

Change a user's role (`registered` | `subscribed` | `admin`). Leaves
`is_verified` untouched. An admin cannot change their own role away from `admin`.

Request: `{ "role": "subscribed" }` → returns the updated user object.

Errors: `role must be one of [...]` (400), `You cannot change your own admin role.` (400), `User not found.` (404).

---

## **POST /api/admin/users/&lt;id&gt;/activate**

Set a user's account activation flag.

Request: `{ "is_verified": true }` → returns the updated user object.

Errors: `Missing required field: 'is_verified'.` (400), `'is_verified' must be a boolean.` (400), `User not found.` (404).

---

## **POST /api/admin/users/&lt;id&gt;/delete**

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
