# Scraping Status API

Admin-only endpoints to monitor scraping operations and get daily summaries.

## Endpoints

### Get Daily Summary

Get aggregated scraping statistics for a specific date.

**URL**: `GET /api/scraping/status/summary`

**Authentication**: JWT Token (Admin role required)

**Query Parameters**:
| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `date`    | string | No       | Date in ISO format (YYYY-MM-DD). Defaults to today. |
| `platform`| string | No       | Filter by platform: `facebook`, `instagram`, `x`, `tiktok`, `linkedin`, `youtube` |

**Response**:
```json
{
  "success": true,
  "data": {
    "date": "2026-07-12",
    "platform_filter": null,
    "total_sessions": 5,
    "sessions_by_status": {
      "pending": 1,
      "completed": 3,
      "failed": 1
    },
    "total_posts_fetched": 150,
    "total_comments_inserted": 1247,
    "total_expected_comments": 1500,
    "comments_ratio": 0.8313,
    "duration_stats": {
      "min_seconds": 45.2,
      "max_seconds": 180.5,
      "avg_seconds": 102.3,
      "min_formatted": "45s",
      "max_formatted": "3m 0s",
      "avg_formatted": "1m 42s"
    },
    "errors": [
      {
        "session_id": "abc-123-def",
        "error": "Connection timeout after 30 seconds..."
      }
    ]
  }
}
```

**Status Codes**:
- `200`: Success
- `400`: Invalid query parameters
- `401`: Missing or invalid token
- `403`: Insufficient permissions (not admin)
- `500`: Database error

**Example**:
```bash
# Get today's summary
curl -H "Authorization: Bearer <jwt_token>" \
  http://localhost:5000/api/scraping/status/summary

# Get summary for a specific date
curl -H "Authorization: Bearer <jwt_token>" \
  "http://localhost:5000/api/scraping/status/summary?date=2026-07-10"

# Get summary for Instagram only
curl -H "Authorization: Bearer <jwt_token>" \
  "http://localhost:5000/api/scraping/status/summary?platform=instagram"
```

---

### Get Sessions for Date

Get detailed list of all scraping sessions for a specific date.

**URL**: `GET /api/scraping/status/sessions`

**Authentication**: JWT Token (Admin role required)

**Query Parameters**:
| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `date`    | string | No       | Date in ISO format (YYYY-MM-DD). Defaults to today. |
| `platform`| string | No       | Filter by platform: `facebook`, `instagram`, `x`, `tiktok`, `linkedin`, `youtube` |

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "session_id": "abc-123-def",
      "created_at": "2026-07-12T10:30:00",
      "completed_at": "2026-07-12T10:32:15",
      "posts_fetched": 50,
      "comments_inserted": 423,
      "status": "completed",
      "error_message": null,
      "duration_seconds": 135.0
    },
    {
      "session_id": "xyz-456-uvw",
      "created_at": "2026-07-12T11:00:00",
      "completed_at": null,
      "posts_fetched": 30,
      "comments_inserted": 0,
      "status": "pending",
      "error_message": null
    },
    {
      "session_id": "err-789-rst",
      "created_at": "2026-07-12T09:00:00",
      "completed_at": null,
      "posts_fetched": 25,
      "comments_inserted": 150,
      "status": "failed",
      "error_message": "Connection timeout"
    }
  ]
}
```

**Status Codes**:
- `200`: Success
- `400`: Invalid query parameters
- `401`: Missing or invalid token
- `403`: Insufficient permissions (not admin)
- `500`: Database error

**Example**:
```bash
# Get all sessions for today
curl -H "Authorization: Bearer <jwt_token>" \
  http://localhost:5000/api/scraping/status/sessions

# Get sessions for a specific date
curl -H "Authorization: Bearer <jwt_token>" \
  "http://localhost:5000/api/scraping/status/sessions?date=2026-07-10"

# Get sessions for Facebook only
curl -H "Authorization: Bearer <jwt_token>" \
  "http://localhost:5000/api/scraping/status/sessions?platform=facebook"
```

---

## Metrics Explained

### comments_ratio

The ratio of comments actually inserted vs expected comments from posts:

```
comments_ratio = total_comments_inserted / total_expected_comments
```

- **total_comments_inserted**: Sum of all comments stored in the database from these sessions
- **total_expected_comments**: Sum of the `comments` field from posts that were scraped (as reported by the social media platform)

A ratio < 1.0 could indicate:
- External scraper didn't capture all comments
- Some comments were filtered (duplicates, invalid data)
- Platform comment count includes deleted/private comments

### duration_stats

Only calculated for **completed** sessions (sessions with both `created_at` and `completed_at` timestamps):

- `min_seconds` / `min_formatted`: Shortest session duration
- `max_seconds` / `max_formatted`: Longest session duration
- `avg_seconds` / `avg_formatted`: Average session duration

---

## Error Handling

Failed sessions include an `error_message` field with details. Common errors:

- **Connection timeout**: External scraper couldn't connect to platform
- **Rate limited**: Platform blocked requests
- **Validation failed**: Comment data didn't match expected schema
- **Database error**: Transaction rolled back

---

## Related Endpoints

- `GET /api/scraping/sessions/<session_id>` - Get details for a specific session (API key auth)
- `GET /api/scraping/posts` - Fetch posts for scraping (API key auth)
- `POST /api/scraping/comments` - Insert scraped comments (API key auth)
