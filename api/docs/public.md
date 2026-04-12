# Public Routes Documentation

All routes in this document are prefixed with `/api/public`.

---

## **GET /api/public/ranking**

Returns public ranking data.

The response is split into:
- `top_global`: top 10 entities globally
- `top_by_category`: top entity per category, excluding entities already in `top_global`

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "top_global": [
      {
        "entity_id": 1,
        "entity_name": "Tesla",
        "category": "automotive",
        "rank": 1
      }
    ],
    "top_by_category": [
      {
        "entity_id": 7,
        "entity_name": "Example Brand",
        "category": "retail",
        "rank": 14
      }
    ]
  }
}
```

### Error Responses

```json
{ "success": false, "error": "No ranking data available" }
```

```json
{ "success": false, "error": "Invalid request data" }
```
