
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

---

## **GET /get_entity_top_posts**

Get top-performing posts for an entity on a specific date. Posts are ranked based on metric gains (compared to the previous available day) using platform-specific weights.

### Request

```
/get_entity_top_posts?entity_id=1&top_posts=5&date=2025-12-31
```

### Query Parameters

- **entity_id** (required, int): The ID of the entity
- **top_posts** (optional, int, default=5): Number of top posts to return (top K)
- **date** (optional, string): Target date for analysis (defaults to today). Posts are filtered to those created within 10 days before this date.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "day": "2025-12-31",
    "posts": [
      {
        "post_id": "12345",
        "platform": "instagram",
        "create_time": "2025-12-30T14:30:00",
        "likes": 5000,
        "comments": 300,
        "shares": 150,
        "gained_likes": 2500,
        "gained_comments": 150,
        "gained_shares": 80,
        "total_score": 15750.0,
        "rank": 1
      },
      {
        "post_id": "67890",
        "platform": "twitter",
        "create_time": "2025-12-31T10:15:00",
        "retweets": 800,
        "likes": 3000,
        "gained_retweets": 500,
        "gained_likes": 1800,
        "total_score": 12300.0,
        "rank": 2
      }
    ]
  }
}
```

### Response Fields

- **day**: The date for which top posts are calculated 
- **posts**: Array of top-performing posts, each containing:
  - **post_id**: Unique identifier for the post
  - **platform**: Social media platform (instagram, twitter, tiktok, youtube, linkedin)
  - **create_time**: When the post was created
  - **[metric_name]**: Current metric values (likes, comments, shares, etc.)
  - **gained_[metric_name]**: Metric increase since previous day
  - **total_score**: Weighted score based on platform-specific metric weights
  - **rank**: Position in the top K ranking (1 = best performing)

### Error Response (400/500)

```json
{
  "error": "Missing required query param: 'entity_id'."
}
```

```json
{
  "error": "Internal server error: details here"
}
```

### Notes

- Posts are only included if they have data from a previous day for comparison
- Posts older than 10 days before the specified date are filtered out
- If no posts are found for the specified date, returns `null`
