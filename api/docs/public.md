# Public Routes Documentation

All routes in this document are prefixed with `/api/public`.

---

## **GET /api/public/ranking**

Returns public ranking data.

The response includes:
- `top_global`: top 10 entities globally

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
