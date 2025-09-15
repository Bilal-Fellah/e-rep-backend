````
# Data Routes Documentation

## **POST /add_category**
Add a new category.

### Request
```json
{
  "name": "Technology",
  "parent_id": 1
}
````

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "id": 5,
    "name": "technology",
    "parent_id": 1
  }
}
```

### Error Responses

```json
{
  "error": "Missing required field: 'name'."
}
```

```json
{
  "error": "Database error details here"
}
```

---

## **POST /delete\_category**

Delete an existing category by ID.

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
{
  "error": "Missing required field: 'id'."
}
```

```json
{
  "error": "No category found with id 5"
}
```

```json
{
  "error": "Database error details here"
}
```

---

## **GET /get\_all\_categories**

Fetch all categories.

### Request

*No body required.*

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "technology", "parent_id": null },
    { "id": 2, "name": "science", "parent_id": null },
    { "id": 3, "name": "ai", "parent_id": 1 }
  ]
}
```

### Error Responses

```json
{
  "error": "No categories found."
}
```

```json
{
  "error": "Database error details here"
}
```

