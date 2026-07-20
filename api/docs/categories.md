# Category Routes Documentation

All routes in this document are prefixed with `/api/data`.

Note: `add_category`, `delete_category`, and `update_category` require the `admin` role. `get_all_categories` and `get_active_categories` remain publicly accessible without a token.

---

## **POST /api/data/add_category**

Add a new category.

### Request

```json
{
  "name": "Technology",
  "name_french": "Technologie",
  "parent_id": 1
}
```

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "id": 5,
    "name": "technology",
    "name_french": "technologie",
    "parent_id": 1,
    "is_active": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required field: 'name'." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/data/delete_category**

Delete a category by id.

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
{ "success": false, "error": "No category found with id 5" }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_all_categories**

Fetch all categories.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "technology", "name_french": "technologie", "parent_id": null, "is_active": true },
    { "id": 2, "name": "science", "name_french": "science", "parent_id": null, "is_active": false }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No categories found." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **GET /api/data/get_active_categories**

Fetch all active categories.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "technology", "name_french": "technologie", "parent_id": null, "is_active": true }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No active categories found." }
```

```json
{ "success": false, "error": "Invalid request data" }
```

---

## **POST /api/data/update_category**

Edit a category and/or toggle its active state. `admin` only.

### Request

```json
{
  "id": 5,
  "name": "Technology",
  "name_french": "Technologie",
  "parent_id": 1,
  "is_active": false
}
```

All fields except `id` are optional; only the fields present are changed. `parent_id` may be `null` (top level). A category cannot be its own parent, and changes that would create a cycle are rejected.

### Success Response (200)

```json
{
  "success": true,
  "data": { "id": 5, "name": "technology", "name_french": "technologie", "parent_id": 1, "is_active": false }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required field: 'id'." }
```

```json
{ "success": false, "error": "'id' must be an integer." }
```

```json
{ "success": false, "error": "A category cannot be its own parent." }
```

```json
{ "success": false, "error": "This change would create a category cycle." }
```

```json
{ "success": false, "error": "No category found with id 5" }
```
