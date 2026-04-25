# Page Routes Documentation

All routes in this document are prefixed with `/api/data`.

Note: role checks are currently commented out in these handlers.

---

## **POST /api/data/add_page**

Create a page for an entity.

### Request

```json
{
  "platform": "twitter",
  "link": "https://twitter.com/example",
  "entity_id": 3,
  "name": "Example Page"
}
```

`name` is optional. If omitted, it defaults to `link`.

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "uuid": "3f5d7c6a-8b10-54c3-a2b5-1c77d33f9e31",
    "name": "Example Page",
    "link": "https://twitter.com/example",
    "platform": "twitter",
    "entity_id": 3
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required fields: 'platform', 'link', or 'entity_id'." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/data/delete_page**

Delete a page by id/uuid.

### Request

```json
{ "id": "3f5d7c6a-8b10-54c3-a2b5-1c77d33f9e31" }
```

### Success Response (200)

```json
{
  "success": true,
  "data": { "deleted_id": "3f5d7c6a-8b10-54c3-a2b5-1c77d33f9e31" }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required field: 'id'." }
```

```json
{ "success": false, "error": "No page found with id <id> or already deleted." }
```

---

## **GET /api/data/get_all_pages**

Fetch all pages.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Example Page",
      "link": "https://twitter.com/example",
      "platform": "twitter",
      "entity_id": 3
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No pages found." }
```

---

## **GET /api/data/get_pages_by_platform**

Fetch pages for one platform.

### Query Parameters

- `platform` (required)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Example Page",
      "link": "https://twitter.com/example",
      "platform": "twitter",
      "entity_id": 3
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query param: 'platform'." }
```

```json
{ "success": false, "error": "No pages found." }
```

---

## **GET /api/data/get_page_interaction_stats**

Get scored interaction stats for posts belonging to one page.

### Query Parameters

- `page_id` (required)
- `start_date` (optional, ISO date string)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "post_id": "7387618805675610113",
      "platform": "linkedin",
      "create_time": "2025-10-26T19:56:45.945Z",
      "score": 53.4
    }
  ]
}
```

Metric fields vary by platform and are included in each item.

### Error Responses

```json
{ "success": false, "error": "No data found for page <page_id>." }
```

```json
{ "success": false, "error": "Invalid request data" }
```
