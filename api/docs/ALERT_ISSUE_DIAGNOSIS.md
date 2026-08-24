# Alert System Issue Diagnosis for Entity 93

## Problem Summary
You created an alert rule for entity 93 to detect negative comments, but you're not seeing any notifications even after running the alerts engine.

## Root Cause
**The alert rule was created AFTER all the negative comments were already processed by the detector.**

### Timeline:
1. **August 21, 2026 @ 19:44:24** - Detector processed all comments and created events
   - 18 events were created for entity 93
   - Detector checkpoint cursor set to: `2026-08-21 19:42:12`
   
2. **August 23, 2026 @ 23:22:17** - Your alert rule was created
   - Rule ID: 2
   - User ID: 14
   - Event Type: negative_comment
   - Entity Scope: {entity_ids: [93]}
   - Status: Active ✅

3. **After August 23** - You ran the detector again
   - Detector checked for NEW comments after `2026-08-21 19:42:12`
   - Found 0 new negative comments
   - Result: No events created, no user alerts generated

## How the Alert System Works

### Event Creation (works correctly ✅)
The detector scans comments and creates `alert_events` when it finds negative comments. These events exist in your database:
- 18 events for entity 93
- All created on August 21st

### User Alert Distribution (the issue ❌)
When an event is created, the system:
1. Calls `AlertRuleRepository.list_matching_rules(event_type, entity_id)`
2. Finds all active rules that match the event
3. Creates a `user_alert` for each matched rule

**The problem:** Events created on August 21st were processed when your rule didn't exist yet. The detector doesn't retroactively create user alerts for old events when new rules are added.

### Checkpoint System
The detector uses checkpoints to track which comments it has already processed:
- Current checkpoint: `2026-08-21 19:42:12`
- The detector only processes comments AFTER this timestamp
- No new negative comments have arrived since then

## Verification Results

### ✅ What's Working:
- Alert rule exists and is active
- Entity 93 has 6 pages across all platforms
- 18 negative comment events exist for entity 93
- Rule matching logic works correctly (Rule 2 matches entity 93)
- Comments are being labeled (label 0 or 1 for negative)

### ❌ What's Not Working:
- No `user_alerts` records exist for user 14
- Events have 0 user alerts attached
- Events were created before the rule existed

## Solutions

### Solution 1: Wait for New Comments (Production Approach)
**Recommended for production**

Simply wait for new comments to arrive. When new comments on entity 93's pages get labeled as negative:
1. The detector will create new events
2. Your rule will be matched
3. User alerts will be created for you

This is the normal flow and requires no intervention.

### Solution 2: Reset Detector Checkpoint (Testing/Development)
**Use for testing or to see historical alerts**

Reset the detector checkpoint to reprocess old comments:

```bash
python reset_detector_checkpoint.py
```

This script will:
1. Set the checkpoint to 10 days ago
2. Make the detector reprocess all comments labeled after that date
3. Create user alerts for your rule retroactively

**⚠️ Warning:** This will create duplicate events if comments are processed multiple times. Only use for development/testing.

### Solution 3: Manual User Alert Creation (Advanced)
Create user alerts manually for existing events:

```sql
INSERT INTO user_alerts (user_id, event_id, rule_id, status, created_at)
SELECT 14, ae.id, 2, 'unread', NOW()
FROM alert_events ae
WHERE ae.entity_id = 93 
  AND ae.event_type = 'negative_comment'
  AND NOT EXISTS (
    SELECT 1 FROM user_alerts ua 
    WHERE ua.user_id = 14 AND ua.event_id = ae.id
  );
```

## Next Steps

### For Testing:
1. Run `python reset_detector_checkpoint.py`
2. Run the alerts engine: `POST /api/alerts/engine/run`
3. Check your alerts: `GET /api/data/alerts`

### For Production:
1. Keep your rule active
2. Wait for new negative comments to arrive
3. The system will automatically create user alerts

## Database Queries Used for Diagnosis

```sql
-- Check alert rule
SELECT * FROM alert_rules WHERE id = 2;

-- Check events
SELECT * FROM alert_events WHERE entity_id = 93 AND event_type = 'negative_comment';

-- Check user alerts (should be empty)
SELECT * FROM user_alerts WHERE user_id = 14;

-- Check detector checkpoint
SELECT * FROM alert_detector_checkpoints WHERE detector_name = 'negative_comment';

-- Check comments
SELECT COUNT(*) 
FROM comments c
JOIN pages p ON c.page_id::uuid = p.uuid
WHERE p.entity_id = 93 AND c.label IN (0, 1);
```

## Files Created for Diagnosis
- `check_alert_93.py` - Comprehensive alert system check
- `check_user_alerts.py` - User alerts distribution check
- `test_rule_matching.py` - Rule matching logic test
- `check_timing.py` - Timeline analysis
- `reset_detector_checkpoint.py` - Checkpoint reset utility

## Conclusion

Your alert system is configured correctly. The issue is purely timing-related: your rule was created after all the negative comments were already processed. The system is designed to alert on NEW events, not historical ones. Once new negative comments arrive, you'll start receiving notifications.
