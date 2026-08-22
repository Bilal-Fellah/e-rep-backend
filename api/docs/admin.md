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
        "user_email": "jane@example.com",
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

## **GET /api/admin/corrections/targets**

Whitelist of what can be corrected, for the admin UI to build a form from.
This is not a generic table editor — only these `(target_type, field)` pairs
can ever be written through this API.

```json
{
  "success": true,
  "data": {
    "targets": {
      "entity": [
        { "field": "name", "label": "Name", "choices": null },
        { "field": "type", "label": "Type", "choices": ["company", "influencer", "small-business"] }
      ],
      "page": [
        { "field": "name", "label": "Name", "choices": null },
        { "field": "link", "label": "Link", "choices": null }
      ],
      "page_history": [
        { "field": "followers", "label": "Followers", "choices": null },
        { "field": "biography", "label": "Biography", "choices": null }
      ],
      "post_metric": [
        { "field": "likes", "label": "Likes", "choices": null },
        { "field": "comments", "label": "Comments", "choices": null },
        { "field": "shares", "label": "Shares", "choices": null }
      ]
    }
  }
}
```

`target_id` is `entities.id` / `pages.uuid` / `pages_history.id` respectively.
`page_history` corrects one top-level key inside that snapshot's scraped
`data` JSON (e.g. a missing follower count) — it does not touch nested
`posts`/`updates`/`top_videos` arrays.

`post_metric` corrects `likes`/`comments`/`shares` on **one post, from one
specific historical snapshot** — i.e. "this post's numbers on this day".
Its `target_id` is the composite string
`"<pages_history_id>:<post_id>"` (e.g. `"482:DGx123"`): the
`pages_history_id` picks the day (find it via `GET /api/admin/pages-history`
or the Pages History admin page, which already shows each snapshot's JSON
including every post's id), and `post_id` is that post's id within that
snapshot's `posts`/`updates`/`top_videos` array (Facebook has no array — its
`pages_history` row *is* the post, so `post_id` there must match that row's
own `post_id`). Not every platform tracks `shares` (instagram, linkedin,
youtube don't) — applying `shares` to one of those returns a 400 naming the
fields that platform does support. On success, `posts_mv`/`posts_history_mv`
are refreshed best-effort after the write commits; a refresh failure never
fails the request (the write already succeeded). Note these two views have
no other scheduled refresh in this codebase — `flask refresh-mv` only
covers `page_posts_metrics_mv` — so on a refresh failure they stay stale
until the next successful `post_metric` correction or a manual
`REFRESH MATERIALIZED VIEW`.

---

## **GET /api/admin/corrections**

History of applied corrections (append-only audit log), newest first.

Query params: `target_type` (`entity` | `page` | `page_history` |
`post_metric`, optional), `limit` (default 50, max 200), `offset`.

```json
{
  "success": true,
  "data": {
    "corrections": [
      {
        "id": 1, "admin_user_id": 3, "target_type": "page_history",
        "target_id": "482", "field": "followers",
        "old_value": null, "new_value": "104200",
        "reason": "Scraper missed the follower count on this run; confirmed via live profile.",
        "created_at": "2026-08-20T10:00:00+00:00"
      }
    ],
    "total": 1, "limit": 50, "offset": 0
  }
}
```

---

## **POST /api/admin/corrections**

Apply one whitelisted correction and log it in the same transaction — the
write and its audit row either both commit or neither does.

### Request

```json
{
  "target_type": "page_history",
  "target_id": "482",
  "field": "followers",
  "new_value": 104200,
  "reason": "Scraper missed the follower count on this run; confirmed via live profile."
}
```

### Behavior

- Validates `target_type`/`field` against the whitelist from
  `/api/admin/corrections/targets`.
- Reads the current value, writes the new one, and inserts an audit row
  (old value, new value, reason, admin, timestamp) — all in one DB
  transaction, so a bad write can never leave an unexplained change.
- `reason` is required and cannot be blank.

### Errors

- `target_type must be one of [...]` (400)
- `'<field>' is not a correctable field for '<target_type>'. Allowed: [...]` (400)
- `A reason is required for every correction.` (400)
- `No <target_type> found with id '<target_id>'.` (400)
- `Value must be a whole number.` (400, for integer fields like `followers`)
- `post_metric target_id must be "<pages_history_id>:<post_id>" ...` (400)
- `'<platform>' posts don't track '<field>'. Supported here: [...]` (400, e.g. `shares` on instagram)
- `No post '<post_id>' found in pages_history #<id>'s '<array_key>'.` (400)

---

## **GET /api/admin/data-integrity/summary**

Read-only null-rate report: how much scraped data is missing, per platform,
so an admin knows where to point `/api/admin/corrections` instead of
guessing. `shares_tracked` is `false` (and `null_shares` is `null`) for
platforms that structurally never collect shares — that's not a data gap,
so it's never counted as one.

`sample_gaps` rows carry the actual scraped values, not just a count — a
bare "followers is null" doesn't tell you whether this is a real scrape
failure or one field, and a bare "likes is missing" doesn't let you check
the real post. `profile_snapshots.sample_gaps` includes `page_link`
(visit the live page), `biography`, and `profile_image` — everything else
that snapshot *did* capture, so an all-empty row reads as "scrape
failed" and a mostly-full row reads as "just this one field." Similarly
`posts.sample_gaps` includes the post's `url`, `caption`, and every metric
this snapshot captured (`likes`/`comments`/`shares`, nulls included) —
click through and compare against the live post.

```json
{
  "success": true,
  "data": {
    "profile_snapshots": {
      "by_platform": [
        { "platform": "instagram", "total": 40, "null_followers": 3 }
      ],
      "sample_gaps": [
        {
          "correction_target_id": "482",
          "platform": "instagram", "page_name": "Acme IG",
          "page_link": "https://instagram.com/acme",
          "recorded_at": "2026-08-19T04:00:00+00:00",
          "biography": "Acme on Instagram",
          "profile_image": "https://.../acme.jpg"
        }
      ]
    },
    "posts": {
      "by_platform": [
        {
          "platform": "instagram", "total": 300,
          "null_likes": 2, "null_comments": 0,
          "shares_tracked": false, "null_shares": null
        }
      ],
      "sample_gaps": [
        {
          "correction_target_id": "500:DGx123",
          "platform": "instagram", "page_name": "Acme IG",
          "recorded_at": "2026-08-19T04:00:00+00:00",
          "missing_fields": ["likes"],
          "url": "https://instagram.com/p/DGx123",
          "caption": "first post",
          "likes": null, "comments": 4,
          "shares": null, "shares_tracked": false
        }
      ]
    }
  }
}
```

Each `sample_gaps[].correction_target_id` can be pasted directly as
`target_id` into `POST /api/admin/corrections` (with `target_type`
`page_history` or `post_metric` respectively) to fix that specific gap.

---

## **GET /api/admin/data-integrity/daily**

Same null rates as `/summary`, broken down by day (`recorded_at`'s date) so
a bad scrape run on one specific date is visible instead of averaged away
across the whole history.

Query params: `days` (default 14, clamped to `[1, 90]`).

```json
{
  "success": true,
  "data": {
    "days": 14,
    "profile_snapshots": [
      { "date": "2026-08-19", "platform": "instagram", "total": 5, "null_followers": 1 }
    ],
    "posts": [
      {
        "date": "2026-08-19", "platform": "instagram", "total": 40,
        "null_likes": 2, "null_comments": 0,
        "shares_tracked": false, "null_shares": null
      }
    ]
  }
}
```

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

---

## **GET /api/admin/posts/created-at/stats**

Get statistics about posts with missing `created_at` values in the database.

**Note:** This shows the raw database state. When `ENABLE_POSTS_CREATED_AT_BACKFILL=true`, these NULL values are filled in-memory before being sent to clients, so users never see missing dates. **The database is never modified** - filling happens at retrieval time only.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "enabled": true,
    "posts_mv": {
      "total": 15234,
      "with_date": 14890,
      "missing_date": 344
    },
    "posts_history_mv": {
      "total": 89456,
      "with_date": 87123,
      "missing_date": 2333
    }
  }
}
```

### Fields

- `enabled` — whether `ENABLE_POSTS_CREATED_AT_BACKFILL=true` in environment
- `posts_mv` — current state (latest snapshot per post) in database
- `posts_history_mv` — all snapshots across time in database
- `missing_date` — counts in database (filled in-memory when users request posts)

---

## In-Memory Posts Date Filling

When `ENABLE_POSTS_CREATED_AT_BACKFILL=true` in environment, missing `created_at` dates are automatically filled **in-memory** when users request posts:

- `GET /api/data/get_post` → fills that specific post (in response only)
- `GET /api/data/get_posts_by_page` → fills all posts in response
- `GET /api/data/get_posts_by_platform` → fills all posts in response
- `GET /api/data/get_posts_by_entity` → fills all posts in response
- `GET /api/data/get_post_history` → fills all snapshots in response

**How it works:**
1. Fetch posts from database (with potential NULL dates)
2. Fill missing dates in-memory using history or fallback logic
3. Return enriched data to client
4. **Database remains unchanged**

**Fill strategy:**
- If any snapshot has `created_at` → use earliest known date for all
- If no snapshot has `created_at` → use `min(recorded_at)` as fallback

**Performance impact:**
- Individual post: ~10ms additional latency
- Page posts: ~50-100ms additional latency
- Zero database modifications

**Safety:**
- Read-only operation (no database writes)
- Errors don't crash requests
- Can be enabled/disabled anytime without risk

See [Posts created_at Fill Documentation](./posts_created_at_backfill.md) for details.
