# Comments API

All routes in this document are prefixed with `/api/data`.

Comments are scraped from social media posts and can be labeled using inference models.

---

## **GET /api/data/get_comments_by_post**

Get all comments for a specific post.

### Query Parameters

- `page_id` (required) - Page UUID
- `platform` (required) - Platform name (e.g., "instagram", "facebook")
- `post_id` (required) - Post ID

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "page_id": "page_uuid",
      "platform": "instagram",
      "post_id": "ABC123",
      "comment_id": "comment_123",
      "text": "Great post!",
      "author_username": "user123",
      "comment_timestamp": "2026-02-24T12:00:00",
      "likes_count": 5,
      "replies_count": 2,
      "label": 1,
      "confidence": 0.95,
      "is_processed": true
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "page_id, platform, and post_id are required" }
```

```json
{ "success": false, "error": "No comments found for this post" }
```

---

## **GET /api/data/get_unprocessed_comments**

Get comments that have not been processed for labeling yet.

### Query Parameters

- `limit` (optional) - Maximum number of comments to return

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "text": "Great post!",
      "is_processed": false,
      "label": null,
      "confidence": null
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "No unprocessed comments found" }
```

---

## **GET /api/data/get_comments_by_label**

Get all comments with a specific label.

### Query Parameters

- `label` (required) - Label value (0-4)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "text": "Great post!",
      "label": 1,
      "confidence": 0.95,
      "is_processed": true
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "label is required" }
```

```json
{ "success": false, "error": "label must be between 0 and 4" }
```

```json
{ "success": false, "error": "No comments found with this label" }
```

---

## **POST /api/data/update_comment_label**

Update the label and confidence for a single comment. Also marks the comment as processed.

### Request Body

```json
{
  "comment_id": 1,
  "label": 1,
  "confidence": 0.95
}
```

### Fields

- `comment_id` (required, integer) - Primary key of the comment
- `label` (required, integer) - Label value (0-4)
- `confidence` (optional, float) - Confidence score (0.0 to 1.0)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "id": 1,
    "text": "Great post!",
    "label": 1,
    "confidence": 0.95,
    "is_processed": true
  }
}
```

### Error Responses

```json
{ "success": false, "error": "comment_id is required" }
```

```json
{ "success": false, "error": "label is required" }
```

```json
{ "success": false, "error": "label must be between 0 and 4" }
```

```json
{ "success": false, "error": "confidence must be between 0.0 and 1.0" }
```

```json
{ "success": false, "error": "Comment not found" }
```

---

## **POST /api/data/bulk_update_comment_labels**

Bulk update labels and confidence scores for multiple comments. Automatically marks all updated comments as processed.

### Request Body

```json
{
  "label_updates": [
    {
      "comment_id": 1,
      "label": 1,
      "confidence": 0.95
    },
    {
      "comment_id": 2,
      "label": 0,
      "confidence": 0.87
    }
  ]
}
```

### Fields

- `label_updates` (required, array) - List of update objects
  - `comment_id` (required, integer) - Primary key of the comment
  - `label` (required, integer) - Label value (0-4)
  - `confidence` (optional, float) - Confidence score (0.0 to 1.0)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "updated_count": 2
  }
}
```

### Error Responses

```json
{ "success": false, "error": "label_updates (list) is required" }
```

```json
{ "success": false, "error": "comment_id is required at index 0" }
```

```json
{ "success": false, "error": "label must be between 0 and 4 at index 1" }
```

---

## **POST /api/data/mark_comments_processed**

Mark multiple comments as processed without updating their labels.

### Request Body

```json
{
  "comment_ids": [1, 2, 3]
}
```

### Fields

- `comment_ids` (required, array of integers) - List of comment primary keys

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "updated_count": 3
  }
}
```

### Error Responses

```json
{ "success": false, "error": "comment_ids (list) is required" }
```

```json
{ "success": false, "error": "All comment_ids must be integers" }
```

---

## **GET /api/data/comment_processing_stats**

Get statistics about comment processing status.

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "total": 1000,
    "processed": 750,
    "unprocessed": 250,
    "labeled": {
      "label_0": 150,
      "label_1": 200,
      "label_2": 100,
      "label_3": 180,
      "label_4": 120
    },
    "unlabeled": 250
  }
}
```
