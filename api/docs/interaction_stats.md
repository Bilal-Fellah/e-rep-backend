# Interaction Stats Routes Documentation

All routes in this document are prefixed with `/api/data`.

---

## **GET /api/data/get_page_interaction_stats**

Return scored interaction stats for posts under a page.

### Query Parameters

- `page_id` (required)
- `start_date` (optional, ISO date)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "post_id": "7387618805675610113",
      "platform": "linkedin",
      "create_time": "2025-10-26T19:56:45.945Z",
      "comments_count": 1,
      "likes_count": 132,
      "score": 53.4
    }
  ]
}
```

Metric keys vary by platform.

### Error Responses

```json
{ "success": false, "error": "No data found for page <page_id>." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_entity_interaction_stats**

Return day-level interaction gains/score summary for one entity.

### Query Parameters

- `entity_id` (required, int)
- `start_date` (optional, ISO datetime/date)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "date": "2025-08-23",
      "total_score": 605.0,
      "platform_scores": {
        "instagram": 368.0,
        "linkedin": 237.0
      },
      "day_gains": {
        "instagram": {
          "comments": 27,
          "likes": 341
        }
      }
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No data found for entity <entity_id>." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/data/get_competitors_interaction_stats**

Return scored post interactions across multiple entities.

### Request Body

```json
{
  "entity_ids": [94, 12],
  "start_date": "2025-11-27"
}
```

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "entity_id": 94,
      "page_id": "page_uuid",
      "post_id": "3770189665996505307",
      "platform": "instagram",
      "create_time": "2025-11-20T18:01:12.000Z",
      "comments": 15,
      "likes": 143,
      "score": 53.4
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "wrong value for entity_ids" }
```

```json
{ "success": false, "error": "No data found for entity [94, 12]." }
```

```json
{ "success": false, "error": "Invalid request data" }
```
