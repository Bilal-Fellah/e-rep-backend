
# Entity Routes Documentation

## **POST /add_entity**
Add a new entity and link it to a category.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request
```json
{
  "name": "Tesla",
  "type": "company",
  "category_id": 2
}
````

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

### Error Response (400/500)

```json
{
  "error": "Missing required fields: 'name', 'type', or 'category_id'."
}
```

```json
{
  "error": "Internal server error: details here"
}
```

---

## **GET /get\_all\_entities**

Fetch all entities.

####   allowed_roles = ["admin", "subscribed", "registered"]

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

### Error Response (404/500)

```json
{
  "error": "No entities found."
}
```

```json
{
  "error": "Internal server error: details here"
}
```

---

## **GET /get\_data\_existing\_entities**

Fetch all entities that have history data.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "tesla", "type": "company" },
    { "id": 2, "name": "apple", "type": "company" }
  ]
}
```

### Error Response (404/500)

```json
{
  "error": "No entities found."
}
```

```json
{
  "error": "Internal server error: details here"
}
```

---

## **POST /delete\_entity**

Delete an entity by ID.

####   allowed_roles = ["admin"]

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

### Error Response (400/404/500)

```json
{
  "error": "Missing required field: 'id'."
}
```

```json
{
  "error": "No entity found with id 5 or already deleted."
}
```

```json
{
  "error": "Internal server error: details here"
}
```

---

## **GET /get\_entity\_profile\_card**

Get entity profile card from history.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_entity_profile_card?entity_id=1
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "entity_id": 1,
    "followers": 100000,
    "platforms": ["twitter", "instagram"]
  }
}
```

### Error Response (404/500)

```json
{
  "error": "no data found for this entity"
}
```

```json
{
  "error": "Internal server error: details here"
}
```

---

## **GET /get\_entity\_followers\_history**

Fetch followers history for an entity.

####  allowed_roles = ["admin", "subscribed"]

### Request

```
/get_entity_followers_history?entity_id=1
```

### Success Response (200)

```json
{
  "success": true,
  "data": [
    { "page_id": 11, "followers": 2000, "date": "2025-09-14", "platform": "twitter" },
    { "page_id": 12, "followers": 5000, "date": "2025-09-14", "platform": "instagram" }
  ]
}
```

### Error Response (400/404/500)

```json
{
  "error": "Missing required query param: 'entity_id'."
}
```

```json
{
  "error": "No history found for this entity."
}
```

```json
{
  "error": "Database error: details here"
}
```

---

## **GET /get\_entity\_followers\_comparison**

Compare followers with other entities in the same category.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_entity_followers_comparison?entity_id=1
```

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "Tesla": {
      "entity_id": 1,
      "records": [
        { "date": "2025-09-14", "platform": "twitter", "followers": 2000 },
        { "date": "2025-09-14", "platform": "instagram", "followers": 5000 }
      ]
    },
    "Apple": {
      "entity_id": 2,
      "records": [
        { "date": "2025-09-14", "platform": "twitter", "followers": 10000 }
      ]
    }
  }
}
```

### Error Response (400/404/500)

```json
{
  "error": "Missing required query param: 'entity_id'."
}
```

```json
{
  "error": "No data for this entity"
}
```

```json
{
  "error": "Database error: details here"
}
```

---

## **POST /compare\_entities\_followers**

Compare followers history between multiple entities.

####   allowed_roles = ["admin", "subscribed", "registered"]

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
        { "date": "2025-09-14", "platform": "twitter", "followers": 2000 }
      ]
    },
    "Apple": {
      "entity_id": 2,
      "records": [
        { "date": "2025-09-14", "platform": "instagram", "followers": 8000 }
      ]
    }
  }
}
```

### Error Response (400/404/500)

```json
{
  "error": "Missing required query param: 'entity_ids'."
}
```

```json
{
  "error": "No data for this entities"
}
```

```json
{
  "error": "Database error: details here"
}
```

---

## **GET /get\_entity\_posts\_timeline**

Fetch recent posts of an entity with optional filters.

####   allowed_roles = ["admin", "subscribed", "registered"]

### Request

```
/get_entity_posts_timeline?entity_id=1&date=2025-09-01&max_posts=5
```

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": "post123",
      "text": "New product launch 🚀",
      "compare_date": "2025-09-14T12:00:00Z",
      "platform": "twitter",
      "page_id": 11,
      "page_name": "Tesla Official"
    },
    {
      "id": "post122",
      "text": "Event highlights",
      "compare_date": "2025-09-13T18:30:00Z",
      "platform": "instagram",
      "page_id": 12,
      "page_name": "Tesla IG"
    }
  ]
}
```

### Error Response (400/404/500)

```json
{
  "error": "Missing required query param: 'entity_id'."
}
```

```json
{
  "error": "Invalid date format provided."
}
```

```json
{
  "error": "No history found for this entity."
}
```

```json
{
  "error": "Unexpected error: details here"
}
```

