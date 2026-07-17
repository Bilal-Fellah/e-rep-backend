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

---

# Sentiment aggregation

The `label` field (0-4) is a **5-point sentiment scale**. The semantic meaning is a
product convention and is **not** encoded in the database:

| label | meaning        |
|-------|----------------|
| 0     | Very Negative  |
| 1     | Negative       |
| 2     | Neutral        |
| 3     | Positive       |
| 4     | Very Positive  |

The endpoints below aggregate this per entity/brand, per post, and across all
entities (ranking). **Only labeled comments** (`label` not null) are counted.
Each summary includes:

- `total` - number of labeled comments in scope
- `counts` / `percentages` - per-label breakdown (`label_0` … `label_4`)
- `score` - single sentiment score in `[-1, 1]`: `(avg_label - 2) / 2`
  (all Very Negative → -1, all Very Positive → +1, all Neutral → 0)
- `positive_share` - percentage of comments labeled Positive or Very Positive (3 or 4)

An empty scope returns `total: 0` with a **200** (not 404) so the frontend can render
an "insufficient data" state.

When **no** window parameter (`period`, `start_date`, `end_date`) is supplied, the window
is **all time** (no bounds).

---

## **GET /api/data/get_entity_comment_sentiment**

Aggregated comment sentiment for one entity/brand, plus a daily trend series and
highest-confidence example comments per label.

### Query Parameters

- `entity_id` (required, integer) - Entity id
- `period` (optional) - Named window resolved server-side: `all`, `yesterday`, `7d`,
  `30d`, `prev_month`, `90d`, `1y`
- `start_date` / `end_date` (optional, ISO `YYYY-MM-DD`) - Explicit window, used when
  `period` is absent

Comments are counted within the resolved `[start_date, end_date]` window (both bounds
inclusive of the whole day).

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "entity_id": 42,
    "total": 320,
    "counts": { "label_0": 20, "label_1": 40, "label_2": 60, "label_3": 120, "label_4": 80 },
    "percentages": { "label_0": 6.3, "label_1": 12.5, "label_2": 18.8, "label_3": 37.5, "label_4": 25.0 },
    "avg_confidence": { "label_0": 0.91, "label_1": 0.88, "label_2": 0.72, "label_3": 0.9, "label_4": 0.93 },
    "score": 0.32,
    "positive_share": 62.5,
    "trend": [
      { "date": "2026-07-01", "label_0": 2, "label_1": 3, "label_2": 5, "label_3": 10, "label_4": 7, "total": 27 }
    ],
    "examples": {
      "label_4": [
        { "id": 1, "text": "Absolutely love this!", "author_username": "user123", "confidence": 0.98, "likes_count": 12, "comment_timestamp": "2026-07-10T09:00:00" }
      ],
      "label_0": []
    }
  }
}
```

### Error Responses

```json
{ "success": false, "error": "entity_id is required" }
```

```json
{ "success": false, "error": "Invalid start_date format. Use ISO format: YYYY-MM-DD." }
```

---

## **GET /api/data/get_post_comment_sentiment**

Aggregated comment sentiment for a single post, plus example comments per label.

### Query Parameters

- `page_id` (required) - Page UUID
- `platform` (required) - Platform name
- `post_id` (required) - Post ID

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "total": 48,
    "counts": { "label_0": 2, "label_1": 6, "label_2": 10, "label_3": 20, "label_4": 10 },
    "percentages": { "label_0": 4.2, "label_1": 12.5, "label_2": 20.8, "label_3": 41.7, "label_4": 20.8 },
    "avg_confidence": { "label_0": 0.9, "label_1": 0.85, "label_2": 0.7, "label_3": 0.92, "label_4": 0.95 },
    "score": 0.31,
    "positive_share": 62.5,
    "examples": { "label_3": [], "label_4": [] }
  }
}
```

### Error Responses

```json
{ "success": false, "error": "page_id, platform, and post_id are required" }
```

---

## **GET /api/data/get_sentiment_ranking**

All entities ranked by `ranking_score` (descending; ties broken by `total`).
`ranking_score` is the raw `score` shrunk toward neutral for small samples
(`score * total / (total + 20)`), so a brand with a couple of glowing comments cannot
outrank a large, steady audience. Brands with fewer than **5** labeled comments are
excluded from the ranking.

**Entitlement-gated** like the other brand rankings: free/registered users may only
request the free time windows (All Time / Last 30 Days) and receive the top-N rows;
premium/admin users get the full list for any window.

### Query Parameters

- `period` (optional) - Named window (`all`, `yesterday`, `7d`, `30d`, `prev_month`,
  `90d`, `1y`)
- `start_date` / `end_date` (optional, ISO `YYYY-MM-DD`) - Explicit window (premium only)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "entity_id": 42,
      "entity_name": "Acme",
      "type": "company",
      "total": 320,
      "counts": { "label_0": 20, "label_1": 40, "label_2": 60, "label_3": 120, "label_4": 80 },
      "percentages": { "label_0": 6.3, "label_1": 12.5, "label_2": 18.8, "label_3": 37.5, "label_4": 25.0 },
      "score": 0.32,
      "ranking_score": 0.3012,
      "positive_share": 62.5,
      "rank": 1
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "This time period is available on a paid plan." }
```

```json
{ "success": false, "error": "Custom date ranges are available on a paid plan." }
```
