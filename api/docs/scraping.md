# Scraping API Documentation

This API provides endpoints for an external scraping service to integrate with the e-rep backend system. The service can fetch posts for scraping and insert scraped comments back into the database.

## Authentication

All endpoints require API key authentication via the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

The API key should be configured in the `.env` file as `SCRAPING_API_KEY`.

## Rate Limiting

- **Limit**: 100 requests per minute per API key
- **Response**: HTTP 429 when limit is exceeded
- **Reset**: Counter resets every 60 seconds

## Endpoints

### 1. Fetch Posts for Scraping

Retrieve a list of posts from the database with optional filters.

**Endpoint**: `GET /api/scraping/posts`

**Query Parameters**:
- `platform` (optional): Filter by platform. Valid values: `facebook`, `instagram`, `x`, `tiktok`, `linkedin`, `youtube`
- `start_date` (optional): Filter posts created after this date (ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`)
- `end_date` (optional): Filter posts created before this date (ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`)

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "posts": [
      {
        "url": "https://instagram.com/p/C12345678",
        "platform": "instagram",
        "comments": 20,
        "likes": 150,
        "content_type": "image",
        "post_id": "C12345678",
        "page_id": "123e4567-e89b-12d3-a456-426614174000",
        "recorded_at": "2024-01-15T10:30:00"
      }
    ],
    "count": 150
  }
}
```

**Error Responses**:
- `400`: Invalid query parameters
```json
{
  "success": false,
  "error": "Invalid platform. Must be one of: facebook, instagram, x, tiktok, linkedin, youtube"
}
```
- `401`: Missing or invalid API key
```json
{
  "success": false,
  "error": "Invalid or missing API key"
}
```
- `429`: Rate limit exceeded
```json
{
  "success": false,
  "error": "Rate limit exceeded. Try again in 30 seconds."
}
```
- `500`: Database error
```json
{
  "success": false,
  "error": "An error occurred in the database."
}
```

**Example cURL**:
```bash
curl -X GET "https://api.example.com/api/scraping/posts?platform=instagram&start_date=2024-01-01T00:00:00Z" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

### 2. Insert Scraped Comments

Insert a batch of scraped comments into the database. All comments are inserted as a single atomic transaction.

**Endpoint**: `POST /api/scraping/comments`

**Request Body**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "comments": [
    {
      "page_id": "123e4567-e89b-12d3-a456-426614174000",
      "platform": "instagram",
      "post_id": "C12345678",
      "id": "18064830815724115",
      "text": "@tatweer.digital شكرا",
      "username": "malek_natsheh99",
      "timestamp": 1783787046,
      "likes": 0,
      "is_reply": true,
      "parent_id": "18094999820577949"
    }
  ]
}
```

**Request Body Schema**:
- `session_id` (string, optional): The session ID from the fetch posts endpoint
- `comments` (array, required): Array of comment objects
  - `page_id` (string, required): Page UUID
  - `platform` (string, required): Platform name
  - `post_id` (string, required): Post ID
  - `id` (string, required): Platform's comment ID
  - `text` (string, required): Comment text content
  - `username` (string, required): Comment author's username
  - `timestamp` (number, required): Unix timestamp when comment was posted
  - `likes` (number, optional): Number of likes (default: 0)
  - `is_reply` (boolean, optional): Whether this is a reply to another comment
  - `parent_id` (string, optional): Parent comment ID for nested replies

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "inserted": 48,
    "skipped": 2,
    "total": 50
  }
}
```

**Response Fields**:
- `session_id`: The session ID (if provided in request)
- `inserted`: Number of new comments inserted
- `skipped`: Number of duplicate comments skipped
- `total`: Total number of comments in the batch

**Error Responses**:
- `400`: Invalid request body or validation failure
```json
{
  "success": false,
  "error": "Validation failed at comment index 5: missing required field 'id'"
}
```
- `401`: Missing or invalid API key
```json
{
  "success": false,
  "error": "Invalid or missing API key"
}
```
- `429`: Rate limit exceeded
```json
{
  "success": false,
  "error": "Rate limit exceeded. Try again in 30 seconds."
}
```
- `500`: Database error (transaction rolled back)
```json
{
  "success": false,
  "error": "An error occurred in the database."
}
```

**Example cURL**:
```bash
curl -X POST "https://api.example.com/api/scraping/comments" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "comments": [
      {
        "page_id": "123e4567-e89b-12d3-a456-426614174000",
        "platform": "instagram",
        "post_id": "C12345678",
        "id": "18064830815724115",
        "text": "@tatweer.digital شكرا",
        "username": "malek_natsheh99",
        "timestamp": 1783787046,
        "likes": 0,
        "is_reply": true,
        "parent_id": "18094999820577949"
      }
    ]
  }'
```

---

### 3. Get Session Details

Retrieve details about a specific scraping session.

**Endpoint**: `GET /api/scraping/sessions/{session_id}`

**Path Parameters**:
- `session_id` (string, required): The session UUID

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2024-01-15T08:00:00",
    "completed_at": "2024-01-15T09:30:00",
    "posts_fetched": 150,
    "comments_inserted": 487,
    "status": "completed",
    "error_message": null
  }
}
```

**Response Fields**:
- `session_id`: Session UUID
- `created_at`: When the session was created (ISO 8601 format)
- `completed_at`: When the session was completed (null if still pending)
- `posts_fetched`: Number of posts fetched in this session
- `comments_inserted`: Number of comments inserted in this session
- `status`: Session status (`pending`, `completed`, or `failed`)
- `error_message`: Error message if status is `failed`

**Error Responses**:
- `401`: Missing or invalid API key
```json
{
  "success": false,
  "error": "Invalid or missing API key"
}
```
- `404`: Session not found
```json
{
  "success": false,
  "error": "Scraping session not found: 550e8400-e29b-41d4-a716-446655440000"
}
```
- `429`: Rate limit exceeded
```json
{
  "success": false,
  "error": "Rate limit exceeded. Try again in 30 seconds."
}
```
- `500`: Database error
```json
{
  "success": false,
  "error": "An error occurred in the database."
}
```

**Example cURL**:
```bash
curl -X GET "https://api.example.com/api/scraping/sessions/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

### 4. Get Today's Scraping Status

Retrieve the status of posts scheduled for scraping today (or a specific date). Categorizes posts scheduled for that date into scraped (already scraped today) and pending (scheduled but not yet scraped).

**Endpoint**: `GET /api/scraping/posts/today-status`

**Query Parameters**:
- `platform` (optional): Filter by platform. Valid values: `facebook`, `instagram`, `x`, `tiktok`, `linkedin`, `youtube`
- `date` (optional): Filter by a specific target date (ISO format YYYY-MM-DD, e.g. `2026-07-13`). Defaults to today's date.

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "date": "2026-07-13",
    "platform_filter": null,
    "scraped_count": 1,
    "pending_count": 1,
    "total_count": 2,
    "scraped_posts": [
      {
        "page_id": "123e4567-e89b-12d3-a456-426614174000",
        "platform": "instagram",
        "post_id": "C12345678",
        "url": "https://instagram.com/p/C12345678",
        "caption": "Test post 1",
        "expected_comments": 10,
        "scraped_comments_count": 5,
        "recorded_at": "2026-07-12T12:00:00",
        "created_at": "2026-07-11T12:00:00"
      }
    ],
    "pending_posts": [
      {
        "page_id": "123e4567-e89b-12d3-a456-426614174001",
        "platform": "facebook",
        "post_id": "FB123456",
        "url": "https://facebook.com/posts/FB123456",
        "caption": "Test post 2",
        "expected_comments": 20,
        "scraped_comments_count": 0,
        "recorded_at": "2026-07-12T12:00:00",
        "created_at": "2026-07-10T12:00:00"
      }
    ]
  }
}
```

**Error Responses**:
- `400`: Invalid query parameters (e.g. invalid platform name or invalid date format)
```json
{
  "success": false,
  "error": "Invalid date format. Use ISO format (YYYY-MM-DD)"
}
```
- `401`: Missing or invalid API key
```json
{
  "success": false,
  "error": "Invalid or missing API key"
}
```
- `429`: Rate limit exceeded
```json
{
  "success": false,
  "error": "Rate limit exceeded. Try again in 30 seconds."
}
```
- `500`: Database error
```json
{
  "success": false,
  "error": "An error occurred in the database."
}
```

**Example cURL**:
```bash
curl -X GET "https://api.example.com/api/scraping/posts/today-status?platform=instagram" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Typical Workflow

1. **Fetch Posts**: Call `GET /api/scraping/posts` to get a list of posts and receive a `session_id`
2. **Scrape Comments**: Use the external scraping service to collect comments for those posts
3. **Insert Comments**: Call `POST /api/scraping/comments` with the scraped comments and the `session_id`
4. **Check Status**: (Optional) Call `GET /api/scraping/sessions/{session_id}` to verify the operation

## Data Integrity

- **Duplicate Detection**: Comments with the same `(page_id, platform, post_id, id)` are automatically skipped
- **Atomic Transactions**: All comments in a batch are inserted as a single transaction. If any error occurs, the entire batch is rolled back
- **Session Tracking**: Each fetch operation creates a session record for audit and troubleshooting

## Error Handling

- All endpoints return structured JSON responses
- HTTP status codes indicate the type of error
- Error messages are descriptive but do not expose internal system details
- Database errors automatically trigger transaction rollback to ensure data consistency
