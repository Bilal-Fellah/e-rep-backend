# Posts API

All routes in this document are prefixed with `/api/data`.

Posts are read-only and served from repository/materialized-view data.

---

## **GET /api/data/get_post**

Get one post by composite key.

### Query Parameters

- `page_id` (required)
- `platform` (required)
- `post_id` (required)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "page_id": "page_uuid",
    "platform": "instagram",
    "post_id": "ABC123"
  }
}
```

### Error Responses

```json
{ "success": false, "error": "page_id, platform, and post_id are required" }
```

```json
{ "success": false, "error": "Post not found" }
```

---

## **GET /api/data/get_posts_by_platform**

Get latest posts for a platform.

### Query Parameters

- `platform` (required)

### Error Responses

```json
{ "success": false, "error": "platform is required" }
```

```json
{ "success": false, "error": "No posts found" }
```

---

## **GET /api/data/get_posts_by_page**

Get latest posts for one page.

### Query Parameters

- `page_id` (required)
- `platform` (optional)

### Error Responses

```json
{ "success": false, "error": "page_id is required" }
```

```json
{ "success": false, "error": "No posts found" }
```

---

## **GET /api/data/get_posts_by_entity**

Get latest posts across all pages under an entity.

### Query Parameters

- `entity_id` (required)
- `platform` (optional)

### Error Responses

```json
{ "success": false, "error": "entity_id is required" }
```

```json
{ "success": false, "error": "No posts found" }
```

---

## **GET /api/data/get_post_history**

Get full snapshot history for one post.

### Query Parameters

- `page_id` (required)
- `platform` (required)
- `post_id` (required)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "page_id": "page_uuid",
      "platform": "instagram",
      "post_id": "ABC123",
      "recorded_at": "2026-02-24T06:00:00"
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "page_id, platform, and post_id are required" }
```

```json
{ "success": false, "error": "No history found for this post" }
```
