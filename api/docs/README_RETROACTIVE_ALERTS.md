# Retroactive Alerts Feature Documentation

## Overview

The retroactive alerts feature allows users to receive notifications for historical events when creating an alert rule.

## Documentation Files

### 1. [RETROACTIVE_ALERTS_FEATURE.md](RETROACTIVE_ALERTS_FEATURE.md)
**Complete Feature Specification**
- Problem statement
- Solution design
- Technical implementation details
- Configuration options
- Decisions made

**Target Audience:** Developers, Technical leads

---

### 2. [RETROACTIVE_ALERTS_IMPLEMENTATION.md](RETROACTIVE_ALERTS_IMPLEMENTATION.md)
**Implementation Summary**
- Files modified
- Code changes
- Implementation checklist
- Testing instructions
- Configuration examples
- Troubleshooting guide

**Target Audience:** Developers implementing or maintaining the feature

---

### 3. [RETROACTIVE_ALERTS_USAGE.md](RETROACTIVE_ALERTS_USAGE.md)
**User Guide**
- How to use the feature
- User scenarios
- API examples
- Best practices
- Common questions
- Frontend integration examples

**Target Audience:** Frontend developers, API consumers

---

### 4. [alerts.md](alerts.md)
**API Documentation**
- Complete alerts API reference
- Request/response formats
- New `include_historical_events` field
- Configuration environment variables

**Target Audience:** API consumers, Frontend developers

---

## Quick Links

### For Developers
- [Feature Specification](RETROACTIVE_ALERTS_FEATURE.md)
- [Implementation Details](RETROACTIVE_ALERTS_IMPLEMENTATION.md)

### For API Consumers
- [API Reference](alerts.md#post-apidataalert-rules)
- [Usage Guide](RETROACTIVE_ALERTS_USAGE.md)

### For Troubleshooting
- [Alert Issue Diagnosis](ALERT_ISSUE_DIAGNOSIS.md)
- Diagnostic scripts: `scripts/diagnostics/`

---

## Quick Start

### API Request
```bash
POST /api/data/alert-rules
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Monitor negative comments",
  "event_type": "negative_comment",
  "entity_scope": {"entity_ids": [93]},
  "include_historical_events": true
}
```

### Response
```json
{
  "success": true,
  "data": {
    "id": 10,
    "name": "Monitor negative comments",
    "historical_alerts_created": 16
  }
}
```

---

## Configuration

Environment variables:
```bash
ALERTS_HISTORICAL_BACKFILL_DAYS=30           # Default time window
ALERTS_HISTORICAL_BACKFILL_MAX_EVENTS=1000   # Default event limit
ALERTS_HISTORICAL_BACKFILL_MODE=sync         # Processing mode
```

---

## Status

✅ **PRODUCTION READY**

- Fully implemented
- Tested and verified
- Well documented
- Backward compatible
