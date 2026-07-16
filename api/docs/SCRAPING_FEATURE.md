# External Scraping Service API

This feature provides secure API endpoints for an external scraping service to integrate with the e-rep backend system. The service can fetch posts for scraping and insert scraped comments back into the database.

## Quick Start

### 1. Create Database Tables

Run the following script to create the necessary tables:

```bash
python scripts/create_scraping_tables.py
```

This creates:
- `comments` table - Stores scraped comments
- `scraping_sessions` table - Tracks scraping operations

### 2. Configure API Key

Generate a secure random key per environment and set it in `.env` (do NOT
commit a real key). For example:

```bash
python -c "import secrets; print('SCRAPING_API_KEY=' + secrets.token_urlsafe(32))"
```

```env
SCRAPING_API_KEY=<your-generated-key>
```

⚠️ **Important**: use a unique random key per environment; never commit it.

### 3. Start the Server

```bash
python app.py
```

### 4. Test the API

Run the integration test script:

```bash
python test_scraping_api.py
```

Or run pytest tests:

```bash
pytest api/tests/integration/test_scraping_api.py -v
```

## API Endpoints

### 1. Fetch Posts for Scraping

**GET** `/api/scraping/posts`

Fetches posts from yesterday's snapshot with optional filters.

**Query Parameters:**
- `platform` (optional): Filter by platform (facebook, instagram, x, tiktok, linkedin, youtube)
- `start_date` (optional): ISO 8601 date (e.g., `2024-01-01T00:00:00Z`)
- `end_date` (optional): ISO 8601 date

**Example:**
```bash
curl -X GET "http://localhost:5000/api/scraping/posts?platform=instagram" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "posts": [...],
    "count": 150
  }
}
```

### 2. Insert Scraped Comments

**POST** `/api/scraping/comments`

Inserts a batch of scraped comments atomically.

**Request Body:**
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

**Example:**
```bash
curl -X POST "http://localhost:5000/api/scraping/comments" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @comments.json
```

**Response:**
```json
{
  "success": true,
  "data": {
    "inserted": 48,
    "skipped": 2,
    "total": 50
  }
}
```

### 3. Get Session Details

**GET** `/api/scraping/sessions/{session_id}`

Retrieves details about a specific scraping session.

**Example:**
```bash
curl -X GET "http://localhost:5000/api/scraping/sessions/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
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

## Features

### 🔒 Authentication
- API key authentication via `Authorization: Bearer {key}` header
- Configurable API key via environment variable
- Rate limiting: 100 requests per minute per API key

### 🔄 Data Integrity
- **Duplicate Detection**: Automatically skips comments with duplicate IDs
- **Atomic Transactions**: All comments in a batch are inserted as one transaction
- **Rollback on Error**: Partial inserts are prevented

### 📊 Session Tracking
- Every post fetch creates a session record
- Track posts fetched and comments inserted
- Monitor session status (pending, completed, failed)

### 🎯 Smart Filtering
- **Yesterday's Snapshot**: Only fetches posts recorded in yesterday's snapshot
- **Platform Filter**: Filter by social media platform
- **Date Range**: Filter by post creation date

## Database Schema

### Comments Table

```sql
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    page_id VARCHAR(36) NOT NULL,
    platform VARCHAR(20) NOT NULL,
    post_id VARCHAR(100) NOT NULL,
    comment_id VARCHAR(100) NOT NULL,
    text TEXT NOT NULL,
    author_username VARCHAR(100) NOT NULL,
    author_profile_url TEXT,
    comment_timestamp TIMESTAMP NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    likes_count BIGINT NOT NULL DEFAULT 0,
    replies_count BIGINT NOT NULL DEFAULT 0,
    parent_comment_id VARCHAR(100),
    scraping_session_id VARCHAR(36),
    extra_data JSONB,
    UNIQUE (page_id, platform, post_id, comment_id)
);
```

### Scraping Sessions Table

```sql
CREATE TABLE scraping_sessions (
    session_id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    posts_fetched INTEGER NOT NULL DEFAULT 0,
    comments_inserted INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    CHECK (status IN ('pending', 'completed', 'failed'))
);
```

## Code Structure

```
api/
├── models/
│   ├── comment_model.py              # Comment ORM model
│   └── scraping_session_model.py     # Session ORM model
├── repositories/
│   ├── comment_repository.py         # Comment data access layer
│   └── scraping_session_repository.py # Session data access layer
├── services/
│   └── scraping_service.py           # Business logic layer
├── routes/
│   └── scraping_routes.py            # API endpoints
├── utils/
│   └── api_key_auth.py               # Authentication & rate limiting
├── docs/
│   └── scraping.md                   # API documentation
└── tests/
    └── integration/
        └── test_scraping_api.py      # Integration tests
```

## Typical Workflow

1. **External Service**: Calls `GET /api/scraping/posts` to fetch posts from yesterday
2. **External Service**: Receives `session_id` and list of posts
3. **External Service**: Scrapes comments for those posts
4. **External Service**: Calls `POST /api/scraping/comments` with scraped data
5. **System**: Validates, de-duplicates, and inserts comments atomically
6. **System**: Updates session record with inserted count
7. **External Service**: (Optional) Calls `GET /api/scraping/sessions/{id}` to verify

## Error Handling

All endpoints return structured JSON responses:

**Success (200)**
```json
{"success": true, "data": {...}}
```

**Client Error (4xx)**
```json
{"success": false, "error": "Descriptive error message"}
```

**Server Error (500)**
```json
{"success": false, "error": "An error occurred in the database."}
```

### Error Codes
- **400**: Validation error (missing fields, invalid data)
- **401**: Authentication error (missing/invalid API key)
- **404**: Resource not found (session doesn't exist)
- **429**: Rate limit exceeded (>100 requests/minute)
- **500**: Database error (transaction rolled back)

## Testing

### Run Integration Tests

```bash
# Run all scraping tests
pytest api/tests/integration/test_scraping_api.py -v

# Run specific test class
pytest api/tests/integration/test_scraping_api.py::TestFetchPosts -v

# Run with coverage
pytest api/tests/integration/test_scraping_api.py --cov=api.services.scraping_service --cov=api.repositories.comment_repository
```

### Manual Testing

Use the provided test script:

```bash
python api/tests/manual/test_scraping_api_manual.py
```

This runs a complete end-to-end test of all endpoints.

## Troubleshooting

### Tables don't exist
Run `python scripts/create_scraping_tables.py`

### Authentication fails
Check that `SCRAPING_API_KEY` is set in `.env` and matches your requests

### No posts returned
The API only returns posts recorded in yesterday's snapshot. Check your `posts_mv` table for yesterday's data.

### Rate limit errors
Rate limit is 100 requests/minute. Wait 60 seconds or restart the server to reset.

## Security Notes

⚠️ **Production Deployment Checklist:**

1. Change `SCRAPING_API_KEY` to a cryptographically secure random key
2. Use HTTPS in production (never send API keys over HTTP)
3. Consider implementing API key rotation
4. Monitor rate limit attempts for potential abuse
5. Set up proper logging and alerting for failed requests
6. Regularly review scraping session logs for anomalies

## Documentation

Full API documentation is available in: `api/docs/scraping.md`

## Support

For issues or questions:
1. Check the error logs in `logs/route-errors-*.jsonl`
2. Review the integration tests for usage examples
3. Consult the API documentation in `api/docs/scraping.md`
