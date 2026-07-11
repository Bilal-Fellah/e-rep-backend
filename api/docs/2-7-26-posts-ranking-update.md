# Posts Ranking Update - Growth-Based Metrics

**Date**: 2026-07-26  
**Impact**: Posts ranking endpoints now use growth-based metrics instead of absolute values

---

## Summary

Posts ranking endpoints have been updated to calculate rankings based on **metric growth** (difference between earliest and latest snapshot) rather than absolute latest values. This aligns with the behavior of company/entity interaction rankings.

---

## Changes Made

### 1. **Ranking Calculation Method**

**Before**:
- Used only the latest snapshot of each post
- Ranked by absolute metric values (total_likes, total_comments, etc.)
- No comparison across time

**After**:
- Tracks multiple snapshots per post across the date window
- Calculates growth: `latest_value - earliest_value`
- Ranks by growth metrics (gained_likes, gained_comments, gained_score, etc.)

### 2. **Response Structure**

**Removed redundant fields**:
- `current_likes`, `current_comments`, `current_shares`, `current_views` (redundant with gained metrics)
- `total_*` aliases now removed from response (kept internally for backward compatibility with order_by_key)

**Added new fields**:
- `window_end` - End date of the ranking window
- `snapshots_count` - Number of snapshots tracked for the post
- `gained_likes` - Growth in likes
- `gained_comments` - Growth in comments
- `gained_shares` - Growth in shares
- `gained_views` - Growth in views
- `gained_score` - Growth in weighted interaction score

**Cleaned response structure**:
```json
{
  "rank": 1,
  "entity_id": 1,
  "entity_name": "Tesla",
  "category": "automotive",
  "root_category": "business",
  "page_id": "page_uuid",
  "page_name": "Tesla Official",
  "page_url": "https://instagram.com/tesla",
  "profile_image_url": "https://example.com/profile.jpg",
  "platform": "instagram",
  "post_id": "post_123",
  "caption": "Launch day update",
  "post_url": "https://instagram.com/p/post_123",
  "created_at": "2026-03-20T10:00:00Z",
  "window_start": "2026-03-14",
  "window_end": "2026-04-14",
  "snapshots_count": 5,
  "gained_likes": 4850,
  "gained_comments": 215,
  "gained_shares": 0,
  "gained_views": 0,
  "gained_score": 5065.0,
  "page_followers": 100000
}
```

### 3. **Affected Endpoints**

All posts ranking endpoints now use growth-based calculation:

- `/api/data/get_posts_interactions_ranking` - Ranked by `gained_score`
- `/api/data/get_posts_likes_ranking` - Ranked by `gained_likes`
- `/api/data/get_posts_comments_ranking` - Ranked by `gained_comments`
- `/api/data/get_posts_followers_ranking` - Ranked by `page_followers` (unchanged)

### 4. **Code Changes**

**File**: `api/services/influence_history_service.py`

- **Method**: `_get_posts_ranking()`
  - Added snapshot tracking across multiple recordings
  - Calculate growth between earliest and latest snapshot
  - Removed redundant response fields
  - Added `window_end` calculation
  - Added `timezone` import for proper date handling

**File**: `api/docs/influence_history.md`

- Updated all posts ranking endpoint documentation
- Added notes about growth calculation methodology
- Updated response examples to reflect new structure
- Clarified metric growth behavior

---

## Benefits

1. **Consistency**: Posts rankings now align with company/entity rankings methodology
2. **More Meaningful**: Growth metrics are more indicative of post performance than absolute values
3. **Cleaner Response**: Removed redundant fields, making the API response more concise
4. **Better Context**: `window_start` and `window_end` clearly define the measurement period

---

## Migration Notes

### For API Consumers

**Breaking Changes**:
- Response no longer includes `total_likes`, `total_comments`, etc. as top-level fields
- Response no longer includes `current_*` fields
- Values now represent **growth** rather than absolute totals

**New Fields**:
- All `gained_*` fields represent growth metrics
- `window_end` added for clarity
- `snapshots_count` indicates data quality

**Backward Compatibility**:
- Query parameters unchanged
- Internal order_by_key mapping preserved
- Ranking logic remains stable

### Example Migration

**Before** (absolute values):
```json
{
  "post_id": "123",
  "total_likes": 5000,
  "total_comments": 200,
  "current_likes": 5000
}
```

**After** (growth values):
```json
{
  "post_id": "123",
  "gained_likes": 850,
  "gained_comments": 45,
  "snapshots_count": 3
}
```

---

## Testing

All 53 unit tests pass, including:
- Entity service tests
- Influence ranking tests
- Top posts bug fix tests
- Utility function tests

No regressions detected.

---

## Related Updates

This update is part of a larger effort that also included:

1. **Top Posts Bug Fix**: First-time posts now correctly included with growth from baseline 0
2. **Test Suite Fixes**: Fixed pre-existing test failures in `test_services.py` and `test_utils.py`
3. **Platform Metrics**: Verified X platform metrics configuration (reposts + likes, no replies)

---

## Technical Details

### Growth Calculation Algorithm

```python
# For each post:
1. Collect all snapshots within date window
2. Sort snapshots by recorded_at (ascending)
3. earliest_snapshot = snapshots[0]
4. latest_snapshot = snapshots[-1]
5. gained_metric = latest_snapshot.metric - earliest_snapshot.metric
6. Rank posts by gained_metric (descending)
```

### Platform-Specific Metrics

Each platform has different tracked metrics:

| Platform | Metrics Used for Score |
|----------|----------------------|
| Instagram | likes, comments |
| LinkedIn | likes_count, comments_count |
| X (Twitter) | likes, reposts |
| TikTok | commentcount, share_count |
| Facebook | likes, num_comments |

### Score Calculation

```python
gained_score = Σ(gained_metric_value × metric_weight)
```

Where `metric_weight` is defined in `platform_metrics` configuration (default = 1.0 per metric).

---

## Files Modified

1. `api/services/influence_history_service.py` - Core ranking logic
2. `api/docs/influence_history.md` - API documentation
3. `api/tests/unit/test_services.py` - Fixed pre-existing test issues
4. `api/tests/unit/test_utils.py` - Fixed period resolver test
5. `api/services/entity_service.py` - Top posts bug fix (first-time posts)
6. `api/tests/unit/test_top_posts_bug.py` - New tests for top posts bug

---

## Contact

For questions or issues related to this update, refer to the codebase or API documentation.
