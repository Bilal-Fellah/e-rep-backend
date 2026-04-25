# Entity Routes Documentation

All routes in this document are prefixed with `/api/data`.

Note: role checks are currently commented out in these handlers.

---

## **POST /api/data/add_entity**

Create an entity and map it to a category.

### Request

```json
{
  "name": "Tesla",
  "type": "company",
  "category_id": 2
}
```

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "entity": {
      "id": 10,
      "name": "tesla",
      "type": "company"
    },
    "entity_category": {
      "entity_id": 10,
      "category_id": 2
    }
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required fields: 'name', 'type', or 'category_id'." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_all_entities**

Fetch all entities.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "tesla", "type": "company" },
    { "id": 2, "name": "spacex", "type": "company" }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No entities found." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_data_existing_entities**

Fetch entities that currently have historical data.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "tesla", "type": "company" }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No entities found." }
```

---

## **POST /api/data/delete_entity**

Delete an entity by id.

### Request

```json
{
  "id": 5
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "deleted_id": 5
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required field: 'id'." }
```

```json
{ "success": false, "error": "No entity found with id 5 or already deleted." }
```

---

## **GET /api/data/get_entity_profile_card**

Get profile-card style entity data derived from history.

### Query Parameters

- `entity_id` (required)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "entity_id": 1
  }
}
```

### Error Responses

```json
{ "success": false, "error": "no data found for this entity" }
```

---

## **GET /api/data/get_entity_followers_history**

Get refined daily followers history for every page under an entity.

### Query Parameters

- `entity_id` (required, int)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "page_id": "page_uuid",
      "followers": 2000,
      "date": "2026-04-01",
      "platform": "instagram"
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'entity_id'." }
```

```json
{ "success": false, "error": "No history found for this entity." }
```

---

## **POST /api/data/compare_entities_followers**

Compare followers history for multiple entities.

### Request

```json
{
  "entity_ids": [1, 2, 3]
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "Tesla": {
      "entity_id": 1,
      "records": [
        { "date": "2026-04-01", "platform": "instagram", "followers": 1000 }
      ]
    }
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required key: 'entity_ids'." }
```

```json
{ "success": false, "error": "No data for this entities" }
```

---

## **GET /api/data/get_entity_likes_history**

Get interpolated daily likes development (gained likes) for each page under an entity.

### Query Parameters

- `entity_id` (required, int)
- `start_date` (optional, ISO date/datetime; default = last 30 days)

### Notes

- Gain calculations use one baseline day before `start_date` (or before the default 30-day window) so the first returned day has a real day-over-day value.
- The baseline day is not returned in the response.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "page_id": "page_uuid",
      "platform": "instagram",
      "date": "2026-04-01",
      "likes_gained": 42
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'entity_id'." }
```

```json
{ "success": false, "error": "No likes development found for this entity." }
```

---

## **POST /api/data/compare_entities_likes**

Compare interpolated daily likes development (gained likes) for multiple entities.

### Request

```json
{
  "entity_ids": [1, 2, 3],
  "start_date": "2026-03-01"
}
```

`start_date` is optional. If omitted, the last 30 days are used.

For each entity, the backend uses one baseline day before the requested window to compute the first returned day's gain accurately.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "Tesla": {
      "entity_id": 1,
      "records": [
        {
          "page_id": "page_uuid",
          "platform": "x",
          "date": "2026-04-01",
          "likes_gained": 18
        }
      ]
    }
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required key: 'entity_ids'." }
```

```json
{ "success": false, "error": "No likes development data for this entities" }
```

---

## **GET /api/data/get_entity_comments_history**

Get interpolated daily comments development (gained comments) for each page under an entity.

### Query Parameters

- `entity_id` (required, int)
- `start_date` (optional, ISO date/datetime; default = last 30 days)

### Notes

- Gain calculations use one baseline day before `start_date` (or before the default 30-day window) so the first returned day has a real day-over-day value.
- The baseline day is not returned in the response.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "page_id": "page_uuid",
      "platform": "instagram",
      "date": "2026-04-01",
      "comments_gained": 11
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'entity_id'." }
```

```json
{ "success": false, "error": "No comments development found for this entity." }
```

---

## **POST /api/data/compare_entities_comments**

Compare interpolated daily comments development (gained comments) for multiple entities.

### Request

```json
{
  "entity_ids": [1, 2, 3],
  "start_date": "2026-03-01"
}
```

`start_date` is optional. If omitted, the last 30 days are used.

For each entity, the backend uses one baseline day before the requested window to compute the first returned day's gain accurately.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "Tesla": {
      "entity_id": 1,
      "records": [
        {
          "page_id": "page_uuid",
          "platform": "linkedin",
          "date": "2026-04-01",
          "comments_gained": 9
        }
      ]
    }
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required key: 'entity_ids'." }
```

```json
{ "success": false, "error": "No comments development data for this entities" }
```

---

## **GET /api/data/get_entity_posts_timeline**

Get recent posts timeline for an entity.

### Query Parameters

- `entity_id` (required, int)
- `date` (optional, ISO date string)
- `max_posts` (optional, int)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "platform": "instagram",
      "page_id": "page_uuid",
      "page_name": "Tesla",
      "compare_date": "2026-04-10T08:20:00+00:00"
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'entity_id'." }
```

```json
{ "success": false, "error": "Invalid date format provided." }
```

```json
{ "success": false, "error": "No history found for this entity." }
```

---

## **GET /api/data/mark_entity_to_scrape**

Marks an entity as ready to scrape.

### Query Parameters

- `entity_id` (required, int)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "message": "true",
    "entity_id": 1
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'entity_id'." }
```

---

## **GET /api/data/get_entity_top_posts**

Gets top performing posts for an entity on a target day, ranked by weighted gained metrics.

### Query Parameters

- `entity_id` (required, int)
- `top_posts` (optional, int, default `5`)
- `date` (optional, `YYYY-MM-DD`)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "day": "2026-04-12",
    "posts": [
      {
        "post_id": "123",
        "platform": "instagram",
        "total_score": 1200.0,
        "rank": 1
      }
    ]
  }
}
```

If there is no comparable data for the selected day, current behavior can return:

```json
{
  "success": true,
  "data": null
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'entity_id'." }
```

```json
{ "success": false, "error": "Invalid request data" }
```
