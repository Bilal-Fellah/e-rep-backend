# How to Use Retroactive Alerts Feature

## Quick Start Guide

The retroactive alerts feature allows users to receive notifications for historical events that occurred before they created their alert rule.

---

## User Scenarios

### Scenario 1: I Want Future Alerts Only (Default Behavior)

**Use Case:** "I want to be notified about negative comments from now on."

**API Request:**
```bash
POST /api/data/alert-rules
Authorization: Bearer <your_jwt_token>
Content-Type: application/json

{
  "name": "Monitor negative comments",
  "event_type": "negative_comment",
  "entity_scope": {"entity_ids": [93]},
  "cooldown_minutes": 60
}
```

**OR explicitly:**
```json
{
  "name": "Monitor negative comments",
  "event_type": "negative_comment",
  "entity_scope": {"entity_ids": [93]},
  "cooldown_minutes": 60,
  "include_historical_events": false
}
```

**Result:**
- No immediate alerts
- Will receive alerts for future negative comments
- `historical_alerts_created: 0`

---

### Scenario 2: I Want to See What I Missed

**Use Case:** "I want to see negative comments from the past 30 days and get notified about future ones."

**API Request:**
```bash
POST /api/data/alert-rules
Authorization: Bearer <your_jwt_token>
Content-Type: application/json

{
  "name": "Monitor negative comments (with history)",
  "event_type": "negative_comment",
  "entity_scope": {"entity_ids": [93]},
  "cooldown_minutes": 60,
  "include_historical_events": true
}
```

**Result:**
- Immediate alerts for past negative comments (last 30 days)
- Will receive alerts for future negative comments
- `historical_alerts_created: 16` (example)

---

### Scenario 3: Multiple Entities

**Use Case:** "I want historical alerts for multiple brands."

**API Request:**
```json
{
  "name": "Monitor brands",
  "event_type": "negative_comment",
  "entity_scope": {"entity_ids": [93, 94, 95]},
  "include_historical_events": true,
  "cooldown_minutes": 60
}
```

**Result:**
- Alerts for all negative comments from entities 93, 94, and 95 (last 30 days)
- Future alerts for all three entities

---

### Scenario 4: Keyword Monitoring

**Use Case:** "I want to see when specific keywords were mentioned."

**API Request:**
```json
{
  "name": "Track risk keywords",
  "event_type": "keyword_mention",
  "keywords": ["boycott", "fraud", "scam"],
  "entity_scope": {"entity_ids": [93]},
  "include_historical_events": true,
  "match_mode": "contains",
  "is_case_sensitive": false,
  "cooldown_minutes": 60
}
```

**Result:**
- Alerts for historical keyword mentions (last 30 days)
- Future alerts when keywords are mentioned
- Uses existing matched keywords from events

---

### Scenario 5: Global Monitoring

**Use Case:** "I want to monitor ALL entities for negative comments."

**API Request:**
```json
{
  "name": "Global negative comment monitor",
  "event_type": "negative_comment",
  "include_historical_events": true,
  "cooldown_minutes": 60
}
```

**Note:** Omit `entity_scope` for global monitoring

**Result:**
- Alerts for negative comments across ALL entities (last 30 days)
- Future alerts for all entities

---

## Understanding the Response

### Success Response

```json
{
  "success": true,
  "data": {
    "id": 10,
    "user_id": 14,
    "name": "Monitor negative comments",
    "event_type": "negative_comment",
    "is_active": true,
    "severity_min": null,
    "entity_scope": {"entity_ids": [93]},
    "cooldown_minutes": 60,
    "match_mode": "contains",
    "is_case_sensitive": false,
    "created_at": "2026-08-24T10:00:00",
    "updated_at": "2026-08-24T10:00:00",
    "keywords": [],
    "historical_alerts_created": 16
  }
}
```

**Key Field:** `historical_alerts_created`
- `0` = No historical events found or feature not enabled
- `> 0` = Number of historical alerts created

---

## Checking Your Alerts

### List All Alerts

```bash
GET /api/data/alerts?limit=20
Authorization: Bearer <your_jwt_token>
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "user_alert_id": 101,
      "status": "unread",
      "created_at": "2026-08-24T10:00:01",
      "event": {
        "id": 625,
        "event_type": "negative_comment",
        "severity": "warning",
        "entity_id": 93,
        "label": 1,
        "event_at": "2026-08-21T19:42:10"
      }
    }
  ]
}
```

### Get Unread Count

```bash
GET /api/data/alerts/unread-count
Authorization: Bearer <your_jwt_token>
```

**Response:**
```json
{
  "success": true,
  "data": {
    "unread": 16
  }
}
```

---

## Configuration (Admin)

Administrators can configure the backfill behavior via environment variables:

### Default Configuration

```bash
# Last 30 days of events
ALERTS_HISTORICAL_BACKFILL_DAYS=30

# Maximum 1000 events per rule
ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS=1000

# Process synchronously
ALERTS_HISTORICAL_BACKFILL_MODE=sync
```

### Conservative Configuration

For systems with limited resources:

```bash
ALERTS_HISTORICAL_BACKFILL_DAYS=7     # Last week only
ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS=100
ALERTS_HISTORICAL_BACKFILL_MODE=sync
```

### Aggressive Configuration

For systems with high capacity:

```bash
ALERTS_HISTORICAL_BACKFILL_DAYS=90    # Last 3 months
ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS=5000
ALERTS_HISTORICAL_BACKFILL_MODE=async  # Future enhancement
```

---

## Best Practices

### 1. Start with Historical Review

When setting up alerts for the first time:
```json
{
  "include_historical_events": true
}
```

This helps you understand the baseline and catch up on what you missed.

### 2. Use Entity Scope

Always specify entity scope when monitoring specific brands:
```json
{
  "entity_scope": {"entity_ids": [93]}
}
```

This prevents overwhelming yourself with alerts from all entities.

### 3. Set Appropriate Cooldowns

Use cooldown to reduce noise:
```json
{
  "cooldown_minutes": 60
}
```

Note: Cooldown is NOT applied to historical backfill.

### 4. Review Historical Alerts First

After creating a rule with `include_historical_events: true`:
1. Check `historical_alerts_created` count
2. Review the alerts
3. Adjust rule settings if needed
4. Mark irrelevant alerts as dismissed

---

## Common Questions

### Q: How far back does it look?
**A:** By default, 30 days. Configurable by admin via `ALERTS_HISTORICAL_BACKFILL_DAYS`.

### Q: Is there a limit?
**A:** Yes, by default 1000 events. Configurable by admin via `ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS`.

### Q: What if I create the same rule twice?
**A:** The second time will find 0 historical events because you already have alerts for them.

### Q: Can I backfill after creating the rule?
**A:** No, backfill only happens during rule creation. Delete and recreate the rule with `include_historical_events: true` if needed.

### Q: Does it respect cooldown?
**A:** No, cooldown is ignored for historical backfill. All matching events create alerts.

### Q: What happens if there are thousands of events?
**A:** The system will backfill up to the configured limit (default 1000) starting with the most recent events.

### Q: Does it work for all event types?
**A:** Yes! Works for:
- `negative_comment`
- `keyword_mention`
- `engagement_anomaly`

---

## Troubleshooting

### Problem: `historical_alerts_created: 0` but I expected more

**Possible Causes:**
1. No events in the last 30 days matching your criteria
2. You already have alerts for those events (from another rule)
3. Entity scope doesn't match any events
4. Admin reduced the lookback period

**Solution:**
Check if events exist:
```sql
SELECT COUNT(*) FROM alert_events
WHERE entity_id = 93 
  AND event_type = 'negative_comment'
  AND event_at >= NOW() - INTERVAL '30 days';
```

### Problem: Too many historical alerts

**Solution:**
Ask admin to reduce configuration:
- Lower `ALERTS_HISTORICAL_BACKFILL_DAYS`
- Lower `ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS`

Or use more specific entity scope:
```json
{
  "entity_scope": {"entity_ids": [93]}  // Instead of global
}
```

### Problem: Missing recent events in backfill

**Solution:**
Ensure the alerts engine has run recently. Historical backfill only works with events that exist in `alert_events` table.

---

## Frontend Integration Example

```javascript
// React example
async function createAlertRule(formData) {
  const response = await fetch('/api/data/alert-rules', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name: formData.name,
      event_type: formData.eventType,
      entity_scope: { entity_ids: formData.entityIds },
      include_historical_events: formData.includeHistorical, // Checkbox value
      cooldown_minutes: formData.cooldown
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    const count = result.data.historical_alerts_created;
    
    if (count > 0) {
      showNotification(`Rule created! ${count} historical alerts added.`);
    } else {
      showNotification(`Rule created! You'll receive alerts for future events.`);
    }
  }
}
```

---

## UI Recommendations

### Rule Creation Form

Add a checkbox:
```
☐ Include historical events from the last 30 days
```

With help text:
```
If checked, you'll receive notifications for past events that match this rule.
This helps you catch up on what you missed.
```

### After Creating Rule

Show feedback:
```
✓ Alert rule created successfully!
📊 16 historical alerts were added
📬 You'll receive notifications for future events
```

---

## Summary

**Default behavior:** Future events only
**With `include_historical_events: true`:** Past + Future events
**Time window:** Last 30 days (configurable)
**Event limit:** 1000 events (configurable)

**When to use historical backfill:**
- ✅ Setting up alerts for the first time
- ✅ Want to see what you missed
- ✅ Reviewing past incidents
- ✅ Auditing historical data

**When NOT to use:**
- ❌ Just want future notifications
- ❌ System is overwhelmed with alerts
- ❌ Historical events are not relevant

---

**Need Help?** Contact support or check the API documentation at `/api/docs/alerts.md`
