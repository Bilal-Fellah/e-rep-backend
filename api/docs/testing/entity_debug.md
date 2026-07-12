# Testing Routes Documentation

All routes in this document are prefixed with `/api/testing`.

These endpoints are intended for internal debugging/testing workflows.

---

## **GET /api/testing/entity_daily_raw_metrics**

Fetch raw daily likes/comments snapshots per post for all pages under an entity.

### Query Parameters

- `entity_id` (required, int)
- `metric` (optional, `likes` or `comments`, default: `likes`)
- `start_date` (optional, ISO date)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "page_id": "p-1",
      "platform": "instagram",
      "date": "2026-01-10",
      "likes_raw": 42,
      "posts_count": 2,
      "per_post": {
        "post-a": 30,
        "post-b": 12
      }
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'entity_id'." }
```

```json
{ "success": false, "error": "Invalid metric. Use 'likes' or 'comments'." }
```

```json
{ "success": false, "error": "No daily raw metrics found for this entity." }
```

---

## **POST /api/testing/update_entity_category**

Replace all current category mappings for an entity with a single new category.

### Request

```json
{
  "entity_id": 12,
  "category_id": 7
}
```

### Behavior

- Validates `entity_id` exists.
- Validates `category_id` exists.
- Removes existing rows for the entity in `entity_category`.
- Inserts one new row with the provided `category_id`.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "entity_id": 12,
    "previous_category_ids": [1, 3],
    "updated_category_id": 7
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required fields: 'entity_id' and 'category_id'." }
```

```json
{ "success": false, "error": "'entity_id' and 'category_id' must be integers." }
```

```json
{ "success": false, "error": "No entity found with id 12." }
```

```json
{ "success": false, "error": "No category found with id 7." }
```
