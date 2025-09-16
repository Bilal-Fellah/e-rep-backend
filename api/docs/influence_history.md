
# Page History Routes Documentation

---

## **GET /get_after_time**
Get all history records created after a given hour.

####   allowed_roles = ["admin"]

### Request
````

/get\_after\_time?hour=12

````

### Success Response (200)
```json
{
  "success": true,
  "data": [
    { "id": 1, "page_id": 10, "data": "some data" },
    { "id": 2, "page_id": 11, "data": "more data" }
  ]
}
````

### Error Responses

```json
{ "error": "No history found" }
```

```json
{ "error": "Internal server error details" }
```

---

## **GET /get\_today\_pages\_history**

Get all page histories for today.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_today_pages_history
```

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "page_id": 5, "data": "some data" },
    { "id": 2, "page_id": 6, "data": "other data" }
  ]
}
```

### Error Responses

```json
{ "error": "No history found" }
```

```json
{ "error": "Internal server error details" }
```

---

## **GET /get\_page\_history\_today**

Get today’s history for a specific page.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_page_history_today?page_id=5
```

### Success Response (200)

```json
{
  "success": true,
  "data": { "id": 1, "page_id": 5, "data": "some data" }
}
```

### Error Responses

```json
{ "error": "No history found" }
```

```json
{ "error": "Internal server error details" }
```

---

## **GET /get\_platform\_history**

Get history for a given platform.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_platform_history?platform=twitter
```

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "page_id": 5, "data": "data 1" },
    { "id": 2, "page_id": 7, "data": "data 2" }
  ]
}
```

### Error Responses

```json
{ "error": "Missing platform parameter" }
```

```json
{ "error": "No history found" }
```

```json
{ "error": "Internal server error details" }
```

---

## **GET /get\_entity\_history**

Get all histories for an entity, optionally filtered by date.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_entity_history?entity_id=3&date=2025-09-15
```

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "page_id": 10, "data": "some data", "date": "2025-09-15T08:00:00" },
    { "id": 2, "page_id": 12, "data": "other data", "date": "2025-09-15T09:30:00" }
  ]
}
```

### Error Responses

```json
{ "error": "Missing required query param: 'entity_id'." }
```

```json
{ "error": "Invalid date format. Use ISO format: YYYY-MM-DD." }
```

```json
{ "error": "No history found for this entity." }
```

```json
{ "error": "Database error: details" }
```

```json
{ "error": "Unexpected error: details" }
```

---

## **GET /get\_entities\_ranking**

Get ranking data for all entities.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_entities_ranking
```

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "entity_id": 1, "score": 95 },
    { "entity_id": 2, "score": 88 }
  ]
}
```

### Error Responses

```json
{ "error": "No data found for entities." }
```

```json
{ "error": "Internal server error: details" }
```
