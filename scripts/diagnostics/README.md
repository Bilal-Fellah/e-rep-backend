# Alert System Diagnostic Scripts

This directory contains diagnostic scripts for troubleshooting the alerts system.

## Scripts

### check_alert_93.py
Comprehensive check for alerts setup for entity 93.
- Checks alert rules
- Checks pages for entity
- Checks labeled comments
- Checks detector checkpoint
- Checks alert events

**Usage:**
```bash
python scripts/diagnostics/check_alert_93.py
```

### check_user_alerts.py
Verifies user alert distribution for a specific user.
- Checks user alerts for user 14
- Verifies event distribution
- Checks rule matching logic

**Usage:**
```bash
python scripts/diagnostics/check_user_alerts.py
```

### check_timing.py
Analyzes timing between rule creation and event creation.
- Compares rule creation time vs event creation time
- Checks detector checkpoint timing
- Identifies timing issues

**Usage:**
```bash
python scripts/diagnostics/check_timing.py
```

### test_rule_matching.py
Tests the rule matching logic.
- Verifies entity scope filtering
- Tests rule matching algorithm
- Simulates repository behavior

**Usage:**
```bash
python scripts/diagnostics/test_rule_matching.py
```

### reset_detector_checkpoint.py
Resets the negative_comment detector checkpoint (for testing/debugging).

**⚠️ Warning:** This will cause the detector to reprocess comments. Use with caution.

**Usage:**
```bash
python scripts/diagnostics/reset_detector_checkpoint.py
```

## Requirements

All scripts require:
- PostgreSQL database connection (localhost:5433)
- Database credentials in `.env` file
- psycopg2 package

## When to Use

Use these scripts when:
- Alerts are not being created as expected
- Investigating timing issues
- Debugging rule matching logic
- Testing detector checkpoint behavior
- Troubleshooting user alert distribution
