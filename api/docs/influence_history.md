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
{ "success": false, "error": "Missing platform parameter" }
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

- This route decodes `access_token` and currently expects a valid token.
- Token errors are handled by shared blueprint handlers.

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

## **GET /api/data/get_entities_ranking**

Return ranking data from the current ranking query.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "entity_id": 1,
      "entity_name": "Tesla",
      "rank": 1
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No data found for entities." }
```

---

## **GET /api/data/entities_ranking**

Return the computed 30-day ranking with platform/follower summary.

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
      "platforms": {},
      "total_score": 1500,
      "average_score": 120.5,
      "total_followers": 100000,
      "total_prev_followers": 98000,
      "rank": 1
    }
  ]
}
```
