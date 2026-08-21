# Alerts API

All routes in this document are backend routes for the alerts feature.

- User-facing routes are prefixed with `/api/data`
- Engine/orchestrator routes are prefixed with `/api/alerts/engine`

---

## Authentication

## 1) User-facing routes (`/api/data/*`)

Use JWT auth (same as other protected data endpoints):

- `Authorization: Bearer <access_token>`

Allowed roles:

- `registered`, `subscribed`, `admin`

## 2) Engine routes (`/api/alerts/engine/*`)

Use service API key:

- `Authorization: Bearer <ALERTS_ENGINE_API_KEY>`

---

## Event Types

Supported event types:

- `negative_comment`
- `keyword_mention`
- `engagement_anomaly`

---

## Rule Payload Reference

`alert-rules` create/update endpoints use this payload shape:

```json
{
  "name": "Brand risk keywords",
  "event_type": "keyword_mention",
  "is_active": true,
  "severity_min": "warning",
  "entity_scope": {
    "entity_ids": [12, 31]
  },
  "cooldown_minutes": 60,
  "match_mode": "contains",
  "is_case_sensitive": false,
  "keywords": ["boycott", "fraud", "scam"]
}
```

Notes:

- `keywords` is required for `keyword_mention` rules.
- `match_mode` allowed: `contains`, `exact`, `regex`
- `entity_scope.entity_ids` is optional. If omitted, rule applies globally.
- `cooldown_minutes` must be `>= 0`.

---

# User-facing Routes (`/api/data`)

## **GET /api/data/alerts**

List current user's alerts.

### Query Parameters

- `status` (optional): `unread`, `read`, `dismissed`
- `event_type` (optional): `negative_comment`, `keyword_mention`, `engagement_anomaly`
- `limit` (optional, default `50`, max `200`)
- `offset` (optional, default `0`)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "user_alert_id": 101,
      "status": "unread",
      "created_at": "2026-08-21T19:50:10.112345",
      "read_at": null,
      "dismissed_at": null,
      "event": {
        "id": 55,
        "event_type": "keyword_mention",
        "severity": "warning",
        "event_at": "2026-08-21T19:49:59.000000",
        "entity_id": 12,
        "page_id": "f3d3a8e8-5f9f-41a7-9f44-6e3f3e2458e2",
        "platform": "instagram",
        "post_id": "C123456",
        "comment_pk": 9001,
        "label": null,
        "matched_keyword": "fraud",
        "payload": {
          "source": "comment",
          "text": "this looks like fraud",
          "keyword_normalized": "fraud",
          "rule_id": 8
        }
      }
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No valid token provided" }
```

```json
{ "success": false, "error": "Insufficient permissions for this action" }
```

---

## **GET /api/data/alerts/unread-count**

Get unread alerts count for current user.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "unread": 7
  }
}
```

---

## **POST /api/data/alerts/{user_alert_id}/read**

Mark one alert as read.

### Path Parameters

- `user_alert_id` (required, integer)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "updated": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Alert not found" }
```

---

## **POST /api/data/alerts/{user_alert_id}/dismiss**

Dismiss one alert.

### Path Parameters

- `user_alert_id` (required, integer)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "updated": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Alert not found" }
```

---

## **POST /api/data/alerts/read-all**

Mark all unread alerts as read.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "updated_count": 12
  }
}
```

---

## **GET /api/data/alert-rules**

List current user's alert rules.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": 8,
      "user_id": 42,
      "name": "Brand risk keywords",
      "event_type": "keyword_mention",
      "is_active": true,
      "severity_min": "warning",
      "entity_scope": { "entity_ids": [12, 31] },
      "cooldown_minutes": 60,
      "match_mode": "contains",
      "is_case_sensitive": false,
      "created_at": "2026-08-21T19:00:00",
      "updated_at": "2026-08-21T19:05:00",
      "keywords": ["boycott", "fraud", "scam"]
    }
  ]
}
```

---

## **POST /api/data/alert-rules**

Create an alert rule for current user.

### Request Body Example

```json
{
  "name": "Negative comments",
  "event_type": "negative_comment",
  "is_active": true,
  "cooldown_minutes": 30
}
```

Keyword example:

```json
{
  "name": "Risk keywords",
  "event_type": "keyword_mention",
  "keywords": ["boycott", "fraud"],
  "match_mode": "contains",
  "is_case_sensitive": false,
  "entity_scope": { "entity_ids": [12] },
  "cooldown_minutes": 60
}
```

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "id": 9,
    "user_id": 42,
    "name": "Risk keywords",
    "event_type": "keyword_mention",
    "is_active": true,
    "severity_min": null,
    "entity_scope": { "entity_ids": [12] },
    "cooldown_minutes": 60,
    "match_mode": "contains",
    "is_case_sensitive": false,
    "created_at": "2026-08-21T20:10:00",
    "updated_at": "2026-08-21T20:10:00",
    "keywords": ["boycott", "fraud"]
  }
}
```

### Error Responses

```json
{ "success": false, "error": "event_type must be one of ['engagement_anomaly', 'keyword_mention', 'negative_comment']" }
```

```json
{ "success": false, "error": "keywords is required for keyword_mention rules" }
```

---

## **PUT /api/data/alert-rules/{rule_id}**

Update an existing alert rule for current user.

### Path Parameters

- `rule_id` (required, integer)

### Request Body Example

```json
{
  "name": "Risk keywords (strict)",
  "match_mode": "exact",
  "keywords": ["fraud", "scam"],
  "cooldown_minutes": 120,
  "is_active": true
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "id": 9,
    "user_id": 42,
    "name": "Risk keywords (strict)",
    "event_type": "keyword_mention",
    "is_active": true,
    "severity_min": null,
    "entity_scope": { "entity_ids": [12] },
    "cooldown_minutes": 120,
    "match_mode": "exact",
    "is_case_sensitive": false,
    "created_at": "2026-08-21T20:10:00",
    "updated_at": "2026-08-21T20:15:00",
    "keywords": ["fraud", "scam"]
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Rule not found" }
```

```json
{ "success": false, "error": "match_mode must be one of ['contains', 'exact', 'regex']" }
```

---

## **DELETE /api/data/alert-rules/{rule_id}**

Delete one alert rule for current user.

### Path Parameters

- `rule_id` (required, integer)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "deleted": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Rule not found" }
```

---

# Engine Routes (`/api/alerts/engine`)

These routes are for external orchestrator/timer service.

## **GET /api/alerts/engine/readiness**

Check if pipeline data is ready for detector execution.

### Success Response (200)

Ready example:

```json
{
  "success": true,
  "data": {
    "ready": true,
    "reason": null,
    "context": {
      "latest_completed_scraping_session": "2cb6b7bb-f016-44ec-b91d-a9c2537066de",
      "latest_completed_at": "2026-08-21T18:55:00",
      "comments_in_session": 1240,
      "post_results_in_session": 450,
      "unprocessed_comments_count": 0,
      "last_mv_refresh_at": "2026-08-21T18:58:00"
    }
  }
}
```

Not-ready example:

```json
{
  "success": true,
  "data": {
    "ready": false,
    "reason": "Latest scraping session is not completed",
    "context": {
      "latest_session_id": "2cb6b7bb-f016-44ec-b91d-a9c2537066de",
      "latest_session_status": "pending"
    }
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Invalid or missing alerts engine API key" }
```

---

## **POST /api/alerts/engine/run**

Run detectors (normally called only when readiness is true).

### Request Body

All detectors:

```json
{
  "dry_run": false
}
```

Selected detectors:

```json
{
  "detectors": ["negative_comment", "keyword_comment", "keyword_post", "engagement_anomaly"],
  "dry_run": false
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "run_at": "2026-08-21T20:25:00.123456",
    "dry_run": false,
    "detectors": {
      "negative_comment": {
        "scanned": 35,
        "events_created": 12,
        "user_alerts_created": 22,
        "cursor_advanced_to": "2026-08-21T20:24:20"
      },
      "keyword_comment": {
        "scanned": 120,
        "events_created": 9,
        "user_alerts_created": 9,
        "cursor_advanced_to": "2026-08-21T20:24:58"
      },
      "keyword_post": {
        "scanned": 40,
        "events_created": 2,
        "user_alerts_created": 2,
        "cursor_advanced_to": "2026-08-21T20:24:50"
      },
      "engagement_anomaly": {
        "scanned": 500,
        "events_created": 3,
        "user_alerts_created": 4,
        "cursor_advanced_to": "2026-08-21T20:00:00"
      }
    },
    "events_created": 26,
    "user_alerts_created": 37
  }
}
```

### Error Responses

```json
{ "success": false, "error": "detectors must be an array" }
```

```json
{ "success": false, "error": "Invalid or missing alerts engine API key" }
```

---

## Operational Notes

- Engagement anomalies ignore suspicious zero metrics (non-zero -> zero transitions).
- Readiness does **not** use a pipeline checkpoint table; it is inferred from existing scraping/comments/MV signals.
- MV refresh marker is written by `flask refresh-mv` and used by readiness checks.
