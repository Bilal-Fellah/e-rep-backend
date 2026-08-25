# Retroactive Alerts Feature Specification

## Problem
When a user creates an alert rule, they only receive notifications for events that occur AFTER the rule is created. Existing events in the database that match the rule are ignored.

## Solution
Add an option during rule creation to backfill user alerts from existing events.

---

## User Experience

### Rule Creation Flow
When creating an alert rule via `POST /api/data/alert-rules`, add new optional field:

```json
{
  "name": "Negative comments monitor",
  "event_type": "negative_comment",
  "entity_scope": {"entity_ids": [93]},
  "include_historical_events": true,  // NEW FIELD
  "cooldown_minutes": 60
}
```

**Field:** `include_historical_events` (boolean, optional, default: `false`)
- `true`: Create user alerts for existing matching events + future events
- `false`: Only create user alerts for future events (current behavior)

---

## Backend Behavior

### On Rule Creation

**When `include_historical_events = true`:**

1. Create the alert rule (existing logic)
2. Query `alert_events` table for matching historical events:
   - Filter by `event_type` matching the rule
   - Filter by `entity_id` in rule's `entity_scope` (if specified)
   - Exclude events that already have a user alert for this user
3. Create `user_alerts` records for each matching event:
   - `user_id`: rule owner
   - `event_id`: matching event ID
   - `rule_id`: newly created rule ID
   - `status`: 'unread'
   - `created_at`: NOW()

**When `include_historical_events = false` or omitted:**
- Use current behavior (no backfill)

### Affected Components

**Models:**
- No changes needed (existing schema supports this)

**API Routes:**
- `POST /api/data/alert-rules` - Accept new field

**Services:**
- `AlertService.create_rule()` - Add backfill logic

**Repositories:**
- `AlertEventRepository` - Add method to fetch historical events matching a rule
- `AlertEventRepository` - Reuse existing `fanout_to_users()` for creating user alerts

---

## Technical Implementation Notes

### Query for Historical Events

```python
def get_historical_events_for_rule(
    event_type: str, 
    entity_scope: dict | None, 
    user_id: int,
    lookback_days: int,
    max_events: int
):
    """
    Fetch events that match rule criteria and don't already have 
    a user alert for this user.
    
    Args:
        event_type: Type of event to match
        entity_scope: Entity filter from rule
        user_id: User ID to check for existing alerts
        lookback_days: Only consider events from last N days
        max_events: Maximum number of events to return
    """
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
    
    q = AlertEvent.query.filter(
        AlertEvent.event_type == event_type,
        AlertEvent.event_at >= cutoff_date  # Time window constraint
    )
    
    # Apply entity scope filter
    if entity_scope and isinstance(entity_scope, dict):
        entity_ids = entity_scope.get('entity_ids')
        if entity_ids:
            q = q.filter(AlertEvent.entity_id.in_(entity_ids))
    
    # Exclude events that already have user alerts for this user
    q = q.outerjoin(
        UserAlert, 
        db.and_(
            UserAlert.event_id == AlertEvent.id,
            UserAlert.user_id == user_id
        )
    ).filter(UserAlert.id.is_(None))
    
    # Order by most recent first and apply limit
    return q.order_by(AlertEvent.event_at.desc()).limit(max_events).all()
```

### Cooldown Considerations
**Decision:** Cooldown is ignored for historical backfill. All matching events create alerts.

---

## API Documentation Update

### POST /api/data/alert-rules

**New Request Field:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `include_historical_events` | boolean | No | `false` | If `true`, creates user alerts for existing events that match this rule |

**Example Request:**

```json
{
  "name": "Track negative sentiment",
  "event_type": "negative_comment",
  "entity_scope": {"entity_ids": [93, 94]},
  "include_historical_events": true,
  "cooldown_minutes": 60
}
```

**Success Response (201):**

```json
{
  "success": true,
  "data": {
    "id": 10,
    "name": "Track negative sentiment",
    "event_type": "negative_comment",
    "entity_scope": {"entity_ids": [93, 94]},
    "is_active": true,
    "cooldown_minutes": 60,
    "created_at": "2026-08-24T10:00:00",
    "historical_alerts_created": 15  // NEW: count of backfilled alerts
  }
}
```

---

## Configuration (Environment Variables)

Add these optional environment variables for admin control:

```bash
# Time window for historical event backfill (in days)
# Default: 30 days
ALERTS_HISTORICAL_BACKFILL_DAYS=30

# Maximum number of historical alerts to create per rule
# Set to 0 for unlimited (not recommended)
# Default: 1000
ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS=1000

# Processing mode for historical backfill
# Values: "sync" (default) or "async"
# Default: sync
ALERTS_HISTORICAL_BACKFILL_MODE=sync
```

**Backfill Logic:**
1. Query events within last N days (from `ALERTS_HISTORICAL_BACKFILL_DAYS`)
2. Limit results to M events (from `ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS`)
3. Process synchronously or asynchronously based on `ALERTS_HISTORICAL_BACKFILL_MODE`

**Note:** Time window is applied first, then limit. If both constraints are set, the system returns the most recent M events from the last N days.

---

## Questions for Clarification

## Decisions Made

### 1. Cooldown Behavior
**Decision:** Cooldown is ignored for historical backfill. All matching events create alerts.

### 2. Backfill Limit
**Decision:** Admin-configurable via environment variables:
- **Time window:** `ALERTS_HISTORICAL_BACKFILL_DAYS` (default: 30 days)
- **Event limit:** `ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS` (default: 1000)
- Both constraints apply: most recent M events from last N days

### 3. Keyword Rules
**Decision:** Use stored `matched_keyword` as-is from historical events. No re-evaluation of keyword matching.

### 4. Processing Mode
**Decision:** Admin-configurable via `ALERTS_HISTORICAL_BACKFILL_MODE`:
- `sync` (default): Synchronous processing
- `async`: Background job processing
- Synchronous is default for immediate user feedback

### 5. Engagement Anomaly Rules
Historical events are valid as-is. No special handling needed.

---

## Implementation Checklist

- [ ] Add environment variables to `.env` file with defaults
- [ ] Add `include_historical_events` field to rule creation payload validation
- [ ] Add helper to read env vars: `ALERTS_HISTORICAL_BACKFILL_DAYS`, `ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS`, `ALERTS_HISTORICAL_BACKFILL_MODE`
- [ ] Add `AlertEventRepository.get_historical_events_for_rule()` method with time window and limit
- [ ] Modify `AlertService.create_rule()` to backfill user alerts when requested (sync/async based on mode)
- [ ] Implement async backfill using background job queue (if async mode enabled)
- [ ] Update API response to include `historical_alerts_created` count
- [ ] Update `api/docs/alerts.md` with new field documentation
- [ ] Add tests for historical backfill logic (sync and async modes)
- [ ] Handle edge cases (no matching events, duplicate prevention)
- [ ] Add batch insert optimization for large backfills

---

## Example Usage

### Scenario: User creates rule for entity 93 on August 24th

**Without historical backfill:**
```json
{"name": "Monitor", "event_type": "negative_comment", "entity_scope": {"entity_ids": [93]}}
```
Result: 0 immediate alerts, will catch future events only

**With historical backfill:**
```json
{
  "name": "Monitor", 
  "event_type": "negative_comment", 
  "entity_scope": {"entity_ids": [93]},
  "include_historical_events": true
}
```
Result: 18 immediate alerts (from events created on August 21st), plus future events
