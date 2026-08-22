# Posts `created_at` In-Memory Fill Documentation

## Overview

Automatic in-memory fill system for missing `created_at` dates in posts. When users request posts, missing dates are filled **in-memory before sending the response**. The database is **never modified** - this is a read-only enrichment layer.

## Problem

Some posts in the database have `NULL` values for the `created_at` field. This happens when:
- The scraped data from social media platforms doesn't include the post creation date
- The date field is in an unexpected format or location in the JSON
- The platform API temporarily doesn't return this field

Missing `created_at` values cause issues with:
- Post sorting and filtering by date
- Analytics and trending calculations
- Time-series analysis of post performance

## Solution

The system fills missing dates **at retrieval time** (in-memory, no database modifications):

### How It Works

```
1. User requests posts → API fetches from database (with NULL dates)
2. PostService checks if filling is enabled
3. If enabled: PostsCreatedAtService fills missing dates in-memory
4. Filled data sent to client
5. Database remains unchanged
```

### Fill Strategy

**Phase 1: Use Known Dates**
For posts where **at least one snapshot** has a `created_at` value:
- Find the earliest known `created_at` from any snapshot
- Use it for all snapshots of that post (in the response only)

**Phase 2: Fallback to Recorded Time**  
For posts where **no snapshot** has a `created_at` value:
- Use the minimum `recorded_at` (earliest snapshot time) as fallback
- This is a conservative estimate that ensures chronological consistency

### Post Identification
Posts are uniquely identified by:
- `page_id` (UUID)
- `platform` (instagram, linkedin, tiktok, youtube, x, facebook)
- `post_id` (platform-specific post identifier)

### Integration Points

Fill happens automatically when:
1. **Individual post retrieval**: `/api/data/get_post` → fills that specific post
2. **Page posts retrieval**: `/api/data/get_posts_by_page` → fills all posts in response
3. **Platform posts**: `/api/data/get_posts_by_platform` → fills all posts in response
4. **Entity posts**: `/api/data/get_posts_by_entity` → fills all posts in response
5. **Post history retrieval**: `/api/data/get_post_history` → fills all snapshots

## Configuration

### Environment Variable

Add to your `.env` file:

```bash
# Enable automatic in-memory fill of missing created_at dates
# Set to 'true' to enable, 'false' to disable (default: false)
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

Accepted values: `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off` (case-insensitive)

### Enabling the Fill

**Development:**
```bash
# In .env file
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

**Production:**
```bash
# Set environment variable on server
export ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

**Docker:**
```yaml
# In docker-compose.yml
environment:
  - ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

## Admin Endpoints

### Check Status

**GET** `/api/admin/posts/created-at/stats`

Get statistics about posts with missing `created_at` values in the database.

**Response:**
```json
{
  "success": true,
  "data": {
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
}
```

**Note:** This shows the raw database state. When filling is enabled, these NULL values are filled in-memory before being sent to clients, so users never see missing dates.

## Performance

### In-Memory Fill Overhead

**Individual Post:**
- Additional latency: <10ms
- Additional query: 1 (to get post history for date lookup)
- Impact: Negligible

**Page Posts (typical: 10-50 posts):**
- Additional latency: 20-100ms
- Additional queries: 1 per post with missing date
- Impact: Low

**Platform/Entity Posts (could be 100s):**
- Additional latency: 50-200ms
- Additional queries: 1 per post with missing date
- Impact: Moderate but acceptable

### Optimization

The service batches queries where possible to minimize database roundtrips. For most use cases, the overhead is barely noticeable.

## How It Works

### Service: `PostsCreatedAtService`

Located: `api/services/posts_created_at_service.py`

**Core Methods:**
- `is_enabled()` - Check if feature is enabled via environment variable
- `fill_missing_dates_for_post_history()` - Fill dates for history snapshots (list)
- `fill_missing_date_for_post()` - Fill date for single post
- `fill_missing_dates_for_posts()` - Fill dates for multiple posts (list)
- `get_missing_dates_stats()` - Get statistics about missing dates in DB

### Integration: `PostService`

Located: `api/services/post_service.py`

All retrieval methods now call the fill service:
```python
def get_post(page_id, platform, post_id):
    post = PostRepository.get_by_composite_key(page_id, platform, post_id)
    if post:
        post = PostsCreatedAtService.fill_missing_date_for_post(post, ...)
    return post
```

### Admin Routes

Located: `api/routes/admin_routes.py`

Endpoint:
- `GET /api/admin/posts/created-at/stats` - View statistics

## Safety Features

**Read-Only Operation:**
- **No database modifications** whatsoever
- Only enriches data in-memory before sending to client
- Database always reflects the original scraped data

**Idempotent:**
- Running multiple times has no side effects
- Can be enabled/disabled anytime without risk

**Non-Blocking:**
- Errors in fill logic don't crash requests
- Falls back gracefully to returning NULL dates
- Logs errors but continues execution

**Zero Risk:**
- Cannot corrupt data
- Cannot cause data inconsistencies
- Cannot affect other services

## Monitoring

### Check if Fill is Active

```bash
# Via admin endpoint
curl -X GET "http://your-domain/api/admin/posts/created-at/stats" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

Look for `"enabled": true` in response.

### Database Query

Check how many posts have missing dates:
```sql
SELECT COUNT(*) 
FROM posts_history_mv 
WHERE created_at IS NULL;
```

**Note:** This count will remain unchanged since filling happens in-memory.

### Application Logs

When filling is enabled and working:
```
[DEBUG] PostsCreatedAtService: Filled 5 missing dates for page request
[DEBUG] PostsCreatedAtService: Using fallback date for post instagram/C123...
```

## Best Practices

### When to Enable

**Enable if:**
- You have posts with missing dates in the database
- You want a clean API response without NULL dates
- You don't want to modify the source database
- Performance overhead (<100ms) is acceptable

**Disable if:**
- All posts have complete dates
- You need absolute minimum latency
- You want to preserve exact database state in API responses
- You're debugging scraping issues and need to see raw data

### Recommended Settings

**Production:**
```bash
# Enable for clean user experience
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

**Development:**
```bash
# Enable to match production behavior
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

**Testing/Debugging:**
```bash
# Disable to see raw database state
ENABLE_POSTS_CREATED_AT_BACKFILL=false
```

## Troubleshooting

### Fill Not Working

**Symptom:** API returns NULL created_at dates

**Solutions:**
1. Check environment variable:
   ```bash
   echo $ENABLE_POSTS_CREATED_AT_BACKFILL
   ```

2. Restart application after changing `.env`:
   ```bash
   # Docker
   docker-compose restart
   
   # Manual
   pkill -f "python.*app.py"
   python app.py
   ```

3. Verify via stats endpoint:
   ```bash
   curl http://localhost:5000/api/admin/posts/created-at/stats
   # Should show "enabled": true
   ```

### Performance Issues

**Symptom:** API responses slower after enabling

**Diagnosis:**
1. Measure latency difference
2. Check how many posts have missing dates (stats endpoint)
3. Review application logs for slow queries

**Solutions:**
1. If only a few posts have missing dates, overhead should be minimal
2. Consider fixing the scraping source to include dates
3. Temporarily disable if performance is critical:
   ```bash
   ENABLE_POSTS_CREATED_AT_BACKFILL=false
   ```

### Dates Still Wrong

**Symptom:** Filled dates don't make sense

**Explanation:**
- Fill uses earliest known `created_at` from any snapshot
- If all snapshots lack `created_at`, uses `recorded_at` as fallback
- The fallback date is when we first scraped it, not when it was actually created

**Solutions:**
- This is expected behavior for posts never scraped with dates
- The fallback is a conservative estimate
- To get accurate dates, fix the scraping source

## Differences from Database Backfill

### In-Memory Fill (This Implementation)
- ✅ No database modifications
- ✅ Zero risk of data corruption
- ✅ Instant enable/disable
- ✅ Works with read-only databases
- ✅ Can be A/B tested easily
- ❌ Adds latency to requests (~10-100ms)
- ❌ Doesn't fix the source data

### Database Backfill (Alternative Approach)
- ❌ Modifies database permanently
- ❌ Risk of incorrect dates persisting
- ❌ Requires careful testing before running
- ❌ Needs write access to database
- ❌ Harder to revert
- ✅ No runtime performance impact
- ✅ Fixes source data permanently

## Technical Details

### Fill Logic for Post History

```python
def fill_missing_dates_for_post_history(history_rows):
    # Find earliest known created_at from snapshots
    known_date = min(row.created_at for row in history_rows if row.created_at)
    
    # Fallback: use earliest recorded_at
    if not known_date:
        known_date = min(row.recorded_at for row in history_rows)
    
    # Fill missing dates in-memory
    for row in history_rows:
        if not row.created_at:
            row.created_at = known_date
    
    return history_rows
```

### Fill Logic for Multiple Posts

```python
def fill_missing_dates_for_posts(posts):
    for post in posts:
        if not post.created_at:
            # Query history to find known date
            history = query_post_history(post.page_id, post.platform, post.post_id)
            known_date = find_earliest_date(history)
            post.created_at = known_date
    
    return posts
```

## Related Documentation

- [Posts Materialized Views](./2-7-26-posts-ranking-update.md) - Design of posts_mv and posts_history_mv
- [Scraping Feature](./SCRAPING_FEATURE.md) - How posts are scraped and stored
- [Admin Dashboard](./admin.md) - Admin management features
- [Database Queries](../database/posts_mv_queries.sql) - Materialized view definitions

## FAQ

**Q: Does this modify my database?**
A: No, this is 100% read-only. It only enriches the data in-memory before sending to clients.

**Q: Will the filled dates be saved?**
A: No, they're computed on-demand for each request.

**Q: What happens if I disable it?**
A: API responses will return NULL for missing dates, just like the database.

**Q: Can I trust the filled dates?**
A: Filled dates are best-effort estimates. They're accurate if at least one snapshot had the real date. Fallback dates (using `recorded_at`) are conservative estimates.

**Q: Should I fix the scraping instead?**
A: Yes, fixing the scraping source is the permanent solution. This feature is a workaround for existing data.

## Last Updated

2026-08-13

## Overview

Automatic backfill system for fixing missing `created_at` dates in posts materialized views (`posts_mv` and `posts_history_mv`). The backfill runs automatically when users request posts data, controlled by an environment variable.

## Problem

Some posts in the database have `NULL` values for the `created_at` field. This happens when:
- The scraped data from social media platforms doesn't include the post creation date
- The date field is in an unexpected format or location in the JSON
- The platform API temporarily doesn't return this field

Missing `created_at` values cause issues with:
- Post sorting and filtering by date
- Analytics and trending calculations
- Time-series analysis of post performance

## Solution

The system implements an automatic, on-demand backfill that runs when posts are retrieved:

### Automatic Backfill Strategy

**Phase 1: Propagate Known Dates**
For posts where **at least one snapshot** has a `created_at` value:
- Use the earliest known `created_at` from any snapshot
- Apply it to all other snapshots of the same post
- Rationale: If we know when a post was created, all snapshots should share the same creation date

**Phase 2: Use Fallback Dates**  
For posts where **no snapshot** has a `created_at` value:
- Use the minimum `recorded_at` (earliest snapshot time) as a fallback
- Rationale: The post must have been created at or before the first time we recorded it
- This is a conservative estimate that ensures chronological consistency

### Post Identification
Posts are uniquely identified by:
- `page_id` (UUID)
- `platform` (instagram, linkedin, tiktok, youtube, x, facebook)
- `post_id` (platform-specific post identifier)

### Integration Points

Backfill is automatically triggered when:
1. **Individual post retrieval**: `/api/data/get_post` → backfills that specific post
2. **Page posts retrieval**: `/api/data/get_posts_by_page` → backfills up to 100 posts for that page
3. **Post history retrieval**: `/api/data/get_post_history` → backfills that specific post

## Configuration

### Environment Variable

Add to your `.env` file:

```bash
# Enable automatic backfill of missing created_at dates in posts
# Set to 'true' to enable, 'false' to disable (default: false)
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

Accepted values: `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off` (case-insensitive)

### Enabling Backfill

**Development:**
```bash
# In .env file
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

**Production:**
```bash
# Set environment variable on server
export ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

**Docker:**
```yaml
# In docker-compose.yml
environment:
  - ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

## Admin Endpoints

### Check Backfill Status

**GET** `/api/admin/posts/created-at/stats`

Get statistics about posts with missing `created_at` values.

**Response:**
```json
{
  "success": true,
  "data": {
    "backfill_enabled": true,
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
}
```

### Manual Bulk Backfill

**POST** `/api/admin/posts/created-at/backfill?batch_size=100&max_posts=1000`

Manually trigger backfill for all posts with missing dates. Use this for:
- Initial backfill of historical data
- Bulk fixes after scraping issues
- Maintenance during low-traffic hours

**Query Parameters:**
- `batch_size` (optional): Posts per batch (default: 100, min: 10, max: 1000)
- `max_posts` (optional): Maximum posts to process (default: unlimited, max: 10000)

**Response:**
```json
{
  "success": true,
  "data": {
    "enabled": true,
    "posts_with_partial_dates": 120,
    "posts_with_no_dates": 224,
    "snapshots_updated_partial": 456,
    "snapshots_updated_none": 1877,
    "total_snapshots_updated": 2333,
    "materialized_view_refreshed": true
  }
}
```

**Error Response (if disabled):**
```json
{
  "success": false,
  "error": "Posts created_at backfill is disabled. Set ENABLE_POSTS_CREATED_AT_BACKFILL=true in environment to enable."
}
```

### Refresh Materialized View

**POST** `/api/admin/posts/created-at/refresh-mv`

Manually refresh the `posts_mv` materialized view. Use after:
- Manual database updates
- Bulk backfill operations
- Data migrations

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "duration_seconds": 12.34
  }
}
```

## How It Works

### Automatic Backfill Flow

```
User Request → PostService → PostsCreatedAtService
                ↓                      ↓
         Check if enabled?    ← Yes → Backfill missing dates
                ↓                      ↓
         Fetch from DB      ← Commit changes
                ↓
         Return to user
```

### Performance Characteristics

**Individual Post Backfill:**
- Impact: Negligible (<10ms additional latency)
- Updates: 0-20 snapshots typically
- When: On every `get_post()` call (if enabled)

**Page Posts Backfill:**
- Impact: Low (<100ms additional latency)
- Updates: Up to 100 posts per request
- When: On every `get_posts_by_page()` call (if enabled)

**Bulk Backfill:**
- Impact: High (minutes for large datasets)
- Updates: Thousands to millions of snapshots
- When: Manual admin trigger only

### Safety Features

**Idempotent Operations:**
- Only updates rows where `created_at IS NULL`
- Safe to run multiple times
- No duplicate updates or data corruption

**Error Handling:**
- Failures don't crash user requests
- Errors are logged but requests continue
- Database rollback on errors

**Transaction Management:**
- Individual post backfills auto-commit
- Page backfills commit after completion
- Bulk backfills commit in batches

## Monitoring

### Check if Backfill is Working

```bash
# Via admin endpoint
curl -X GET "http://your-domain/api/admin/posts/created-at/stats" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Application Logs

When backfill is enabled, look for:
```
[INFO] PostsCreatedAtService: Backfilled 5 snapshots for post instagram/C1234...
[INFO] PostsCreatedAtService: Backfilled 23 posts for page 550e8400-e29b...
```

### Database Query

Check remaining missing dates:
```sql
SELECT COUNT(*) 
FROM posts_history_mv 
WHERE created_at IS NULL;
```

## Best Practices

### When to Enable

**Enable if:**
- You have historical posts with missing dates
- Scraping occasionally misses date fields
- You need complete temporal data for analytics

**Disable if:**
- All posts have complete dates
- Performance is critical (microseconds matter)
- You want manual control over data quality

### Recommended Settings

**Production:**
```bash
# Enable automatic backfill for seamless data quality
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

**Development:**
```bash
# Enable to test backfill behavior
ENABLE_POSTS_CREATED_AT_BACKFILL=true
```

**Testing:**
```bash
# Disable to test with raw data
ENABLE_POSTS_CREATED_AT_BACKFILL=false
```

### Initial Setup

1. **Check current state:**
   ```bash
   GET /api/admin/posts/created-at/stats
   ```

2. **Enable backfill:**
   ```bash
   # Add to .env
   ENABLE_POSTS_CREATED_AT_BACKFILL=true
   ```

3. **Run bulk backfill once (optional):**
   ```bash
   POST /api/admin/posts/created-at/backfill
   ```

4. **Verify results:**
   ```bash
   GET /api/admin/posts/created-at/stats
   ```

5. **Monitor automatic backfill:**
   - Check application logs
   - Monitor database query patterns
   - Verify API response times

## Troubleshooting

### Backfill Not Working

**Symptom:** Stats show missing dates but they're not being filled

**Solutions:**
1. Check environment variable:
   ```bash
   echo $ENABLE_POSTS_CREATED_AT_BACKFILL
   ```

2. Restart application after changing `.env`:
   ```bash
   # Docker
   docker-compose restart
   
   # Manual
   pkill -f "python.*app.py"
   python app.py
   ```

3. Check logs for errors:
   ```bash
   grep "PostsCreatedAtService" logs/app.log
   ```

### Performance Degradation

**Symptom:** API responses slower after enabling backfill

**Solutions:**
1. Monitor which endpoints are slow:
   - Individual posts: Should be <10ms overhead
   - Page posts: Should be <100ms overhead

2. Disable backfill temporarily:
   ```bash
   ENABLE_POSTS_CREATED_AT_BACKFILL=false
   ```

3. Run bulk backfill during off-hours instead:
   ```bash
   # Disable automatic
   ENABLE_POSTS_CREATED_AT_BACKFILL=false
   
   # Run manual bulk backfill at 3 AM
   cron: 0 3 * * * curl -X POST http://localhost/api/admin/posts/created-at/backfill
   ```

### Some Posts Still Missing Dates

**Symptom:** After backfill, verification shows remaining NULL dates

**Cause:** 
- New posts scraped without dates
- Posts added during backfill
- Platform-specific date parsing issues

**Solutions:**
1. Re-run bulk backfill:
   ```bash
   POST /api/admin/posts/created-at/backfill
   ```

2. Check if specific platforms have issues:
   ```sql
   SELECT platform, COUNT(*) 
   FROM posts_history_mv 
   WHERE created_at IS NULL 
   GROUP BY platform;
   ```

3. Investigate scraping logic for problematic platforms

### Materialized View Out of Sync

**Symptom:** `posts_mv` doesn't reflect backfilled dates

**Solution:** Manually refresh:
```bash
POST /api/admin/posts/created-at/refresh-mv
```

## Technical Details

### Service: `PostsCreatedAtService`

Located: `api/services/posts_created_at_service.py`

**Methods:**
- `is_backfill_enabled()` - Check if feature is enabled
- `get_missing_dates_stats()` - Get statistics
- `backfill_post_dates()` - Backfill single post
- `backfill_page_posts_dates()` - Backfill page posts
- `backfill_all_missing_dates()` - Bulk backfill
- `refresh_posts_mv()` - Refresh materialized view

### Integration: `PostService`

Located: `api/services/post_service.py`

Modified methods with automatic backfill:
- `get_post()` - Backfills single post before retrieval
- `get_posts_by_page()` - Backfills page posts before retrieval
- `get_post_history()` - Backfills post history before retrieval

### Admin Routes

Located: `api/routes/admin_routes.py`

Endpoints:
- `GET /api/admin/posts/created-at/stats` - Statistics
- `POST /api/admin/posts/created-at/backfill` - Manual backfill
- `POST /api/admin/posts/created-at/refresh-mv` - Refresh MV

## Related Documentation

- [Posts Materialized Views](./2-7-26-posts-ranking-update.md) - Design of posts_mv and posts_history_mv
- [Scraping Feature](./SCRAPING_FEATURE.md) - How posts are scraped and stored
- [Admin Dashboard](./admin.md) - Admin management features
- [Database Queries](../database/posts_mv_queries.sql) - Materialized view definitions

## Last Updated

2026-08-13
