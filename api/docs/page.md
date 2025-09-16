# Page Routes Documentation

---

## **POST /add_page**
Add a new page.
####   allowed_roles = ["admin", "subscribed", "registered"]

### Request
```json
{
  "platform": "twitter",
  "link": "https://twitter.com/example",
  "entity_id": 3,
  "name": "Example Page"
}
````

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
{ "error": "Missing required fields: 'platform', 'link', or 'entity_id'." }
```

```json
{ "error": "Internal server error details" }
```

---

## **POST /delete\_page**

Delete an existing page by ID.

####   allowed_roles = ["admin"]

### Request

```json
{ "id": 5 }
```

### Success Response (200)

```json
{
  "success": true,
  "data": { "deleted_id": 5 }
}
```

### Error Responses

```json
{ "error": "Missing required field: 'id'." }
```

```json
{ "error": "No page found with id 5 or already deleted." }
```

```json
{ "error": "Internal server error details" }
```

---

## **GET /get\_all\_pages**

Fetch all pages.

####   allowed_roles = ["admin", "subscribed", "registered"]


### Request

```
/get_all_pages
```

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
    },
    {
      "uuid": "789e4567-e89b-12d3-a456-426614174999",
      "name": "Another Page",
      "link": "https://facebook.com/example",
      "platform": "facebook",
      "entity_id": 4
    }
  ]
}
```

### Error Responses

```json
{ "error": "No pages found." }
```

```json
{ "error": "Internal server error details" }
```

---

## **GET /get\_pages\_by\_platform**

Fetch all pages for a given platform.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_pages_by_platform?platform=twitter
```

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
{ "error": "No pages found." }
```

```json
{ "error": "Internal server error details" }
```

