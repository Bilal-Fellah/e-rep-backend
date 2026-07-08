# Influence History Routes Documentation

All routes in this document are prefixed with `/api/data`.

---

## **GET /api/data/get_platform_history**

Return history records for a platform.

### Query Parameters

- `platform` (required)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "page_id": "page_uuid",
      "data": {},
      "recorded_at": "2026-04-12T09:00:00"
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'platform'." }
```

```json
{ "success": false, "error": "No history found" }
```

---

## **GET /api/data/get_entity_history**

Return entity history by date (today by default).

### Query Parameters

- `entity_id` (required, int)
- `date` (optional, `YYYY-MM-DD`)

### Notes

- This route no longer requires a token. The previous JWT check has been removed.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "page_id": "page_uuid",
      "data": {},
      "date": "2026-04-12T09:00:00"
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'entity_id'." }
```

```json
{ "success": false, "error": "Invalid date format. Use ISO format: YYYY-MM-DD." }
```

```json
{ "success": false, "error": "No history found for this entity." }
```

```json
{ "success": false, "error": "Token has expired" }
```

```json
{ "success": false, "error": "Invalid token" }
```

---

## **GET /api/data/get_followers_ranking**

Return followers-based entity ranking data.

### Query Parameters

- `date` (optional, string; default `1m`)
  - Allowed values: `7d`, `1m`, `3m`
  - `7d` = 7 days before today
  - `1m` = 1 month before today (30-day window)
  - `3m` = 3 months before today (90-day window)

### Notes

- Uses followers snapshots only.
- Ranking is computed as of the requested day (relative to today).
- If a page has no data on the requested day, the nearest previous and next
  snapshot days are averaged to estimate the followers count.
- Does not compute post-based score fields.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "entity_id": 1,
      "entity_name": "Tesla",
      "total_followers": 100000,
      "rank": 1,
      "category": "business",
      "platforms": {
        "facebook": {
          "page_id": "page_uuid",
          "followers": 50000,
          "profile_url": "https://example.com/profile.jpg",
          "page_url": "https://facebook.com/example"
        }
      }
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No followers ranking data found for entities." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_posts_followers_ranking**

Return globally ranked posts ordered by the followers of the page that published them.

### Query Parameters

- `period` (optional, string; e.g. `7d`, `1m`, `3m`) — mutually exclusive with `start_date`/`end_date`.
- `start_date` (optional, ISO date/datetime)
- `end_date` (optional, ISO date/datetime)

### Notes

- Uses the latest post snapshot found inside the selected window.
- `total_followers` reflects the publisher page followers for that post snapshot.
- Response shape follows the entity-ranking style: ranked list with `rank`, entity metadata, page metadata, and metric totals.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "post_id": "post_123",
      "entity_id": 1,
      "entity_name": "Tesla",
      "category": "automotive",
      "root_category": "business",
      "window_start": "2026-03-14",
      "page_id": "page_uuid",
      "page_name": "Tesla Official",
      "platform": "instagram",
      "caption": "Launch day update",
      "total_followers": 100000,
      "rank": 1
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No followers ranking data found for posts." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_posts_interactions_ranking**

Return globally ranked posts ordered by weighted interaction score.

### Query Parameters

- `period` (optional, string; e.g. `7d`, `1m`, `3m`) — mutually exclusive with `start_date`/`end_date`.
- `start_date` (optional, ISO date/datetime)
- `end_date` (optional, ISO date/datetime)

### Notes

- Uses the same scoring idea as the entity interactions ranking.
- `total_score` is the weighted sum of the post's interaction metrics for its platform.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "post_id": "post_123",
      "entity_id": 1,
      "entity_name": "Tesla",
      "category": "automotive",
      "root_category": "business",
      "window_start": "2026-03-14",
      "page_id": "page_uuid",
      "page_name": "Tesla Official",
      "platform": "instagram",
      "caption": "Launch day update",
      "total_score": 1234.5,
      "rank": 1
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No interactions ranking data found for posts." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_posts_likes_ranking**

Return globally ranked posts ordered by total likes.

### Query Parameters

- `period` (optional, string; e.g. `7d`, `1m`, `3m`) — mutually exclusive with `start_date`/`end_date`.
- `start_date` (optional, ISO date/datetime)
- `end_date` (optional, ISO date/datetime)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "post_id": "post_123",
      "entity_id": 1,
      "entity_name": "Tesla",
      "category": "automotive",
      "root_category": "business",
      "window_start": "2026-03-14",
      "page_id": "page_uuid",
      "page_name": "Tesla Official",
      "platform": "instagram",
      "caption": "Launch day update",
      "total_likes": 5000,
      "rank": 1
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No likes ranking data found for posts." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_posts_comments_ranking**

Return globally ranked posts ordered by total comments.

### Query Parameters

- `period` (optional, string; e.g. `7d`, `1m`, `3m`) — mutually exclusive with `start_date`/`end_date`.
- `start_date` (optional, ISO date/datetime)
- `end_date` (optional, ISO date/datetime)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "post_id": "post_123",
      "entity_id": 1,
      "entity_name": "Tesla",
      "category": "automotive",
      "root_category": "business",
      "window_start": "2026-03-14",
      "page_id": "page_uuid",
      "page_name": "Tesla Official",
      "platform": "instagram",
      "caption": "Launch day update",
      "total_comments": 900,
      "rank": 1
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No comments ranking data found for posts." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_followers_progress_ranking**

Return followers progress (gain) ranking for entities over a time window.

### Query Parameters

- `period` (optional, string; e.g. `7d`, `1m`, `3m`) — mutually exclusive with `start_date`/`end_date`.
- `start_date` (optional, ISO date/datetime)
- `end_date` (optional, ISO date/datetime)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "entity_id": 1,
      "entity_name": "Tesla",
      "followers_gained": 5000,
      "rank": 1
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No followers progress ranking data found for entities." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_interactions_ranking**

Return company interactions ranking using post materialized views.

### Query Parameters

- `start_date` (optional, ISO date/datetime; default = last 30 days)

### Notes

- Only entities where `type = company` and `to_scrape = true` are included.
- Ranking is computed from `posts_mv` aggregates using platform metric weights.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "entity_id": 1,
      "entity_name": "Tesla",
      "category": "automotive",
      "root_category": "business",
      "window_start": "2026-03-14",
      "total_score": 1234.5,
      "total_posts": 42,
      "total_likes": 10000,
      "total_comments": 800,
      "total_shares": 250,
      "total_views": 90000,
      "rank": 1,
      "platforms": {
        "instagram": {
          "posts_count": 12,
          "likes": 3000,
          "comments": 250,
          "shares": 0,
          "views": 0,
          "score": 1350
        }
      }
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No interactions ranking data found for companies." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_likes_ranking**

Return company ranking ordered by total likes in the selected window.

### Query Parameters

- `start_date` (optional, ISO date/datetime; default = last 30 days)

### Notes

- Uses the same response shape and data source as `get_interactions_ranking`.
- Ranking order is based on `total_likes` (descending).

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "entity_id": 1,
      "entity_name": "Tesla",
      "category": "automotive",
      "root_category": "business",
      "window_start": "2026-03-14",
      "total_score": 1234.5,
      "total_posts": 42,
      "total_likes": 10000,
      "total_comments": 800,
      "total_shares": 250,
      "total_views": 90000,
      "rank": 1,
      "platforms": {
        "instagram": {
          "posts_count": 12,
          "likes": 3000,
          "comments": 250,
          "shares": 0,
          "views": 0,
          "score": 1350
        }
      }
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No likes ranking data found for companies." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_comments_ranking**

Return company ranking ordered by total comments in the selected window.

### Query Parameters

- `start_date` (optional, ISO date/datetime; default = last 30 days)

### Notes

- Uses the same response shape and data source as `get_interactions_ranking`.
- Ranking order is based on `total_comments` (descending).

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "entity_id": 1,
      "entity_name": "Tesla",
      "category": "automotive",
      "root_category": "business",
      "window_start": "2026-03-14",
      "total_score": 1234.5,
      "total_posts": 42,
      "total_likes": 10000,
      "total_comments": 800,
      "total_shares": 250,
      "total_views": 90000,
      "rank": 1,
      "platforms": {
        "instagram": {
          "posts_count": 12,
          "likes": 3000,
          "comments": 250,
          "shares": 0,
          "views": 0,
          "score": 1350
        }
      }
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No comments ranking data found for companies." }
```

```json
{ "success": false, "error": "Invalid request data" }
```
