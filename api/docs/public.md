# Public Routes Documentation

All routes in this document are prefixed with `/api/public`.

---

## Caching

Every API response carries an explicit `Cache-Control`. The default, applied by
the `after_request` hook in `api/utils/cache_control.py`, is `no-store` — that
covers all of `/api/data`, `/api/auth`, `/api/admin`, `/api/scraping` and
`/health`, none of which may be stored by a browser or intermediary.

`/api/public/ranking` is the one opt-in, via `@cache_public`. Its 200 responses
are `public, max-age=300, s-maxage=300, stale-while-revalidate=600`; its 4xx
responses fall back to `no-store` so a transient empty-data 404 can't be cached
for five minutes. flask-cors emits `Vary: Origin` alongside it.

Opt another route in only if its body is identical for every caller — no
session, no JWT, no per-user state.

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
