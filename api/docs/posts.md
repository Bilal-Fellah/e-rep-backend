# Posts API

All routes are prefixed with `/data`.

Posts are read-only — they are sourced from the `posts_mv` and `posts_history_mv` materialized views, which are refreshed after each scrape cycle. There are no create / update / delete endpoints.

**Supported platforms:** `instagram`, `linkedin`, `tiktok`, `youtube`, `x`, `facebook`

---

## Post Object

```json
{
  "page_id": "uuid",
  "platform": "instagram",
  "post_id": "ABC123",
  "created_at": "2026-01-15T10:30:00",
  "recorded_at": "2026-02-24T06:00:00",
  "url": "https://...",
  "likes": 1500,
  "comments": 42,
  "shares": null,
  "views": null,
  "caption": "Post caption text",
  "content_type": "photo",
  "image_url": "https://...",
  "video_url": null,
  "is_pinned": false,
  "extra_data": { ...full original scrape JSON... }
}
```

`recorded_at` is the timestamp of the scrape snapshot the metrics come from.

---

## **GET /data/get_post**

Get a single post by its composite key.

### Query Parameters

| Param | Type | Required |
|-------|------|----------|
| `page_id` | UUID string | ✅ |
| `platform` | string | ✅ |
| `post_id` | string | ✅ |

### Success Response (200)

```json
{
  "success": true,
  "data": { ...post object... }
}
```

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"page_id, platform, and post_id are required"` |
| 404 | `"Post not found"` |

---

## **GET /data/get_posts_by_platform**

Get all latest posts for a given platform.

### Query Parameters

| Param | Type | Required |
|-------|------|----------|
| `platform` | string | ✅ |

### Success Response (200)

```json
{
  "success": true,
  "data": [ ...array of post objects... ]
}
```

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"platform is required"` |
| 404 | `"No posts found"` |

---

## **GET /data/get_posts_by_page**

Get all latest posts for a specific page.

### Query Parameters

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `page_id` | UUID string | ✅ | |
| `platform` | string | ❌ | Filter by platform if provided |

### Success Response (200)

```json
{
  "success": true,
  "data": [ ...array of post objects, ordered by created_at desc... ]
}
```

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"page_id is required"` |
| 404 | `"No posts found"` |

---

## **GET /data/get_posts_by_entity**

Get all latest posts across every page belonging to an entity.

### Query Parameters

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `entity_id` | integer | ✅ | |
| `platform` | string | ❌ | Filter by platform if provided |

### Success Response (200)

```json
{
  "success": true,
  "data": [ ...array of post objects, ordered by created_at desc... ]
}
```

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"entity_id is required"` |
| 404 | `"No posts found"` |

---

## **GET /data/get_post_history**

Get the full time-series snapshot history for a single post from `posts_history_mv`. Each entry is one scrape snapshot — useful for tracking metric changes over time.

### Query Parameters

| Param | Type | Required |
|-------|------|----------|
| `page_id` | UUID string | ✅ |
| `platform` | string | ✅ |
| `post_id` | string | ✅ |

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "page_id": "uuid",
      "platform": "instagram",
      "post_id": "ABC123",
      "recorded_at": "2026-02-24T06:00:00",
      "created_at": "2026-01-15T10:30:00",
      "likes": 1500,
      "comments": 42,
      "shares": null,
      "views": null,
      "url": "https://...",
      "caption": "...",
      "content_type": "photo",
      "image_url": "https://...",
      "video_url": null,
      "is_pinned": false,
      "extra_data": {}
    }
  ]
}
```

Results are ordered by `recorded_at DESC` (newest first).

### Error Responses

| Status | Message |
|--------|---------|
| 400 | `"page_id, platform, and post_id are required"` |
| 404 | `"No history found for this post"` |
