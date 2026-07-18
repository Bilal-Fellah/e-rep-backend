# Public Routes Documentation

All routes in this document are prefixed with `/api/public`.

---

## **GET /api/public/ranking**

Returns public ranking data.

The response includes:
- `top_global`: top 10 entities for the requested scope

### Query Parameters

- `type` (optional; one of `company`, `influencer`, `small-business`) — narrow the preview to a single entity kind. When omitted, all entity types are ranked together. Used by the Brendex influencer teaser (`?type=influencer`).

### Success Response (200)

Each row includes a `type` field (the entity's kind).

```json
{
  "success": true,
  "data": {
    "top_global": [
      {
        "entity_id": 1,
        "entity_name": "Tesla",
        "type": "company",
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
