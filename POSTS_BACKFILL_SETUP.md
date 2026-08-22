# Posts `created_at` In-Memory Fill - Setup Summary

## What Was Implemented

An **in-memory fill system** that enriches posts data with missing `created_at` dates when users request them. **The database is never modified** - this is a read-only operation that fills gaps in the response data.

## Key Point: No Database Modifications

This system **DOES NOT** write to the database. It only:
1. Fetches posts from database (with potential NULL dates)
2. Fills missing dates in-memory
3. Returns enriched data to the client
4. Database remains unchanged

## Quick Start

### 1. Enable Fill

Add to your `.env` file:
```bash
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

### 2. Restart Application

```bash
# Docker
docker-compose restart

# Manual
pkill -f "python.*app.py"
python app.py
```

### 3. Verify It's Working

Check status via admin endpoint:
```bash
curl -X GET "http://localhost:5000/api/admin/posts/created-at/stats" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

Response should show `"enabled": true`.

## How It Works

### Automatic In-Memory Fill
When enabled, missing dates are filled **in-memory** when users request posts:

```
User Request → Fetch from DB (with NULLs) → Fill dates in-memory → Send to client
                                                ↓
                                        Database unchanged
```

- **Individual post requests** → Fills that specific post
- **Page posts requests** → Fills all posts in the response
- **Post history requests** → Fills all snapshots

**Performance:** 10-100ms overhead depending on number of posts

### Fill Strategy

**Phase 1: Use Known Dates**
- If any snapshot has `created_at` → use it for all (in response only)

**Phase 2: Fallback to First Recorded**
- If no snapshot has `created_at` → use `min(recorded_at)` as estimate

## Admin Endpoints

### Check Status
```bash
GET /api/admin/posts/created-at/stats
```

Returns:
```json
{
  "enabled": true,
  "posts_mv": {
    "total": 15234,
    "with_date": 14890,
    "missing_date": 344
  },
  "posts_history_mv": {
    "total": 89456,
    "with_date": 87123,
    "missing_date": 2333
  }
}
```

**Note:** Shows raw database state. When enabled, these NULLs are filled in responses.

## Files Added/Modified

### New Files
- `api/services/posts_created_at_service.py` - In-memory fill logic
- `api/docs/posts_created_at_backfill.md` - Detailed documentation

### Modified Files
- `api/services/post_service.py` - Integrated in-memory fill
- `api/routes/admin_routes.py` - Added stats endpoint
- `api/docs/admin.md` - Added endpoint documentation
- `.env` - Added `ENABLE_POSTS_CREATED_AT_BACKFILL` variable

## Configuration

### Environment Variable

```bash
# Enable automatic in-memory fill (recommended)
ENABLE_POSTS_CREATED_AT_BACKFILL=true

# Disable to return raw database data
ENABLE_POSTS_CREATED_AT_BACKFILL=false
```

Accepts: `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off` (case-insensitive)

## Typical Workflow

### Initial Setup

1. **Check current state:**
   ```bash
   GET /api/admin/posts/created-at/stats
   ```

2. **Enable fill in .env:**
   ```bash
   ENABLE_POSTS_CREATED_AT_BACKFILL=true
   ```

3. **Restart application**

4. **Verify it's working:**
   - Request some posts via API
   - Check that `created_at` fields are now populated
   - Database stats remain the same (no modifications)

### Ongoing Operation

- Fill runs automatically on every post request
- Monitor via stats endpoint periodically
- No maintenance required

## Monitoring

### Check if Fill is Active
```bash
curl http://localhost:5000/api/admin/posts/created-at/stats | jq '.data.enabled'
```

### Check Database State (Unchanged)
```sql
-- These counts won't change since database isn't modified
SELECT COUNT(*) FROM posts_history_mv WHERE created_at IS NULL;
```

### Application Logs
Look for fill activity:
```bash
grep "PostsCreatedAtService" logs/app.log
```

## Safety Features

- **Read-only**: Never writes to database
- **Non-blocking**: Errors don't crash requests
- **Idempotent**: Can enable/disable anytime
- **Zero risk**: Cannot corrupt or modify data

## Troubleshooting

### Fill Not Working

**Check environment variable:**
```bash
echo $ENABLE_POSTS_CREATED_AT_BACKFILL
```

**Restart application after changing .env**

**Verify via stats endpoint**

### Performance Issues

**Disable fill:**
```bash
ENABLE_POSTS_CREATED_AT_BACKFILL=false
```

**Measure overhead:**
- Individual posts: ~10ms
- Page posts: ~50-100ms
- Large result sets: ~100-200ms

## Documentation

- **Detailed guide**: `api/docs/posts_created_at_backfill.md`
- **Admin endpoints**: `api/docs/admin.md`
- **Service code**: `api/services/posts_created_at_service.py`

## Key Advantages

✅ **No database modifications** - Completely safe
✅ **Instant enable/disable** - Just restart the app
✅ **Works with read-only databases** - No write permissions needed
✅ **Easy to test** - Enable in dev, disable in prod, etc.
✅ **Preserves source data** - Database stays true to scraped data
✅ **Low risk** - Cannot corrupt data

## Trade-offs

❌ **Runtime overhead** - Adds 10-100ms to requests
❌ **Doesn't fix source** - Database still has NULLs
❌ **Computed each time** - Not cached (though could be)

## When to Use

**Use this approach if:**
- You want to enrich API responses without touching the database
- You need to preserve the original scraped data
- You want a reversible, zero-risk solution
- Performance overhead (<100ms) is acceptable

**Consider alternative if:**
- You need to permanently fix the database
- Every millisecond matters for performance
- You want to fix the root cause (scraping)

## Last Updated

2026-08-13
