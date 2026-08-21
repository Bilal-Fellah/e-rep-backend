# Alerts Feature

This document covers the implemented backend alerts system, how to run it in
production with an external systemd timer runner, and what remains to be done
outside this repository.

---

## 1) What is implemented

### Event families

- `negative_comment`
  - Trigger: comment label updated to `0` or `1`
- `keyword_mention`
  - Trigger: configured keyword matched in:
    - comment text
    - post caption (`posts_mv.caption`)
- `engagement_anomaly`
  - Trigger: abnormal increase/drop in post engagement history
  - Mandatory noise guard: suspicious zeros are ignored (e.g. non-zero -> 0)

### Persistence model

Implemented tables:

- `alert_rules`
- `alert_rule_keywords`
- `alert_events`
- `user_alerts`
- `alert_detector_checkpoints`

And a new column on `comments`:

- `label_updated_at`

Migration file:

- `migrations/versions/h9i0j1k2l3m4_add_alerts_feature_tables.py`

---

## 2) API surface

## 2.1 User-facing APIs (JWT)

Prefix: `/api/data`

- `GET /alerts`
- `GET /alerts/unread-count`
- `POST /alerts/{user_alert_id}/read`
- `POST /alerts/{user_alert_id}/dismiss`
- `POST /alerts/read-all`

Rules:

- `GET /alert-rules`
- `POST /alert-rules`
- `PUT /alert-rules/{rule_id}`
- `DELETE /alert-rules/{rule_id}`

Auth roles allowed:

- `registered`, `subscribed`, `admin`

## 2.2 Engine/orchestration APIs (service API key)

Prefix: `/api/alerts/engine`

- `GET /readiness`
- `POST /run`

Used by the external timer service.

---

## 3) Security model for external runner

Implemented a dedicated API-key decorator:

- `require_alerts_engine_api_key`

Expected header:

- `Authorization: Bearer <ALERTS_ENGINE_API_KEY>`

Do not reuse scraping key. Keep separate:

- `SCRAPING_API_KEY`: scraping service endpoints
- `ALERTS_ENGINE_API_KEY`: alerts engine endpoints

Both use constant-time comparison and in-memory per-key rate limiting.

---

## 4) Readiness logic (no pipeline checkpoint table)

Per your chosen design, there is **no** `pipeline_checkpoints` table.

`GET /api/alerts/engine/readiness` returns ready only if all checks pass:

1. Latest scraping session exists and is `completed`
2. Latest completed session is fresh enough
3. Latest session has data evidence:
   - comments for that session OR scraping post-results for that session
4. Unprocessed comments backlog is not above threshold
5. Materialized view refresh marker exists and is newer than latest completed scrape

The MV marker is persisted in `alert_detector_checkpoints` under
`detector_name = "mv_refresh"`, updated from `flask refresh-mv`.

### Readiness config

- `ALERTS_READINESS_FRESHNESS_MINUTES` (default `180`)
- `ALERTS_READINESS_MAX_UNPROCESSED` (default `0`)

---

## 5) Keyword matching details

Keyword rules support match modes:

- `contains` (default)
- `exact`
- `regex`

Normalization used for non-case-sensitive matching:

1. trim
2. collapse multiple spaces
3. lowercase

Matching behavior:

- If `is_case_sensitive = false`:
  - compares normalized text and normalized keyword
- If `is_case_sensitive = true`:
  - compares normalized spacing but preserves case

Keyword events use dedupe keys:

- comment: `kw:c:{comment_pk}:{keyword_normalized}`
- post: `kw:p:{page_id}:{platform}:{post_id}:{keyword_normalized}`

---

## 6) Engagement anomaly detector

Detector name: `engagement_anomaly`

Source: `posts_history_mv` grouped by `(page_id, platform, post_id)`

Metrics evaluated:

- `likes`, `comments`, `shares`, `views`

Method:

- Build a baseline from previous valid points (median)
- Compare latest point against baseline
- Trigger on configured thresholds for increase/drop

### Zero-value noise protection (implemented)

A metric point is treated as suspicious and ignored when:

- previous valid value > 0
- current value == 0

Such points are excluded from:

- anomaly trigger
- baseline construction

This prevents scraper-error zeros from creating false drop alerts.

### Engagement config

- `ALERTS_ENGAGEMENT_LOOKBACK_DAYS` (default `8`)
- `ALERTS_ENGAGEMENT_MIN_BASELINE` (default `20`)
- `ALERTS_ENGAGEMENT_THRESHOLD_UP` (default `0.50` => +50%)
- `ALERTS_ENGAGEMENT_THRESHOLD_DOWN` (default `0.50` => -50%)
- `ALERTS_ENGAGEMENT_MIN_ABS_CHANGE` (default `10`)

---

## 7) External systemd runner (what you must set up)

This repo now provides the APIs and includes a runnable script template:

- `scripts/alerts_engine_runner.py`

Deploy that script on the external timer host.

## 7.1 Minimal runner flow

1. `GET /api/alerts/engine/readiness`
2. if `ready=false`: exit 0
3. if `ready=true`: `POST /api/alerts/engine/run`
4. log summary

## 7.2 Suggested env file on runner host

`/etc/brendex/alerts-runner.env`

```env
BACKEND_URL=https://your-backend-url
ALERTS_ENGINE_API_KEY=your-strong-secret
RUN_DRY=false
```

## 7.3 systemd unit/timer (example)

`/etc/systemd/system/brendex-alert-runner.service`

```ini
[Unit]
Description=Brendex Alerts Runner
After=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/brendex/alerts-runner.env
ExecStart=/usr/bin/python3 /opt/brendex-alert-runner/run_alerts.py
User=brendex
Group=brendex
```

`/etc/systemd/system/brendex-alert-runner.timer`

```ini
[Unit]
Description=Run Brendex Alerts Runner every 10 minutes

[Timer]
OnCalendar=*:0/10
Persistent=true
Unit=brendex-alert-runner.service

[Install]
WantedBy=timers.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now brendex-alert-runner.timer
sudo systemctl status brendex-alert-runner.timer
```

---

## 8) Rule payload examples

### 8.1 Negative comments for all entities

```json
{
  "name": "Negative comments",
  "event_type": "negative_comment",
  "is_active": true,
  "cooldown_minutes": 30
}
```

### 8.2 Keyword mentions scoped to entities

```json
{
  "name": "Brand risk keywords",
  "event_type": "keyword_mention",
  "keywords": ["boycott", "scam", "fraud"],
  "match_mode": "contains",
  "is_case_sensitive": false,
  "entity_scope": {"entity_ids": [12, 31]},
  "cooldown_minutes": 60
}
```

### 8.3 Engagement anomalies

```json
{
  "name": "Engagement anomalies",
  "event_type": "engagement_anomaly",
  "entity_scope": {"entity_ids": [12]},
  "cooldown_minutes": 120
}
```

---

## 9) Notes on idempotency

- `alert_events.dedupe_key` is unique
- `user_alerts` has a uniqueness constraint on `(user_id, event_id, rule_id)`
- detector checkpoints persist cursor timestamps per detector

This makes repeated timer calls safe.

---

## 10) Remaining tasks for full production readiness

These are outside code already added here:

1. Set `ALERTS_ENGINE_API_KEY` in backend environment
2. Deploy + run DB migration
3. Ensure your daily/intraday pipeline always runs `flask refresh-mv`
   - this now updates the MV refresh marker used by readiness
4. Deploy external runner host/script/systemd timer
5. Add frontend alerts UI page + polling
6. Add observability dashboards/alerts for:
   - readiness false reasons
   - detector run errors
   - events per detector over time

---

## 11) Files added/changed

### Added

- `api/models/alert_rule_model.py`
- `api/models/alert_rule_keyword_model.py`
- `api/models/alert_event_model.py`
- `api/models/user_alert_model.py`
- `api/models/alert_detector_checkpoint_model.py`
- `api/repositories/alert_rule_repository.py`
- `api/repositories/alert_event_repository.py`
- `api/repositories/alert_detector_checkpoint_repository.py`
- `api/services/alert_service.py`
- `api/services/alert_engine_service.py`
- `api/routes/alerts_engine_routes.py`
- `api/routes/data/alerts.py`
- `migrations/versions/h9i0j1k2l3m4_add_alerts_feature_tables.py`

### Updated

- `api/models/comment_model.py`
- `api/repositories/comment_repository.py`
- `api/models/__init__.py`
- `api/__init__.py`
- `api/routes/__init__.py`
- `api/routes/data/__init__.py`
- `api/utils/api_key_auth.py`
- `api/utils/permissions.py`
- `README.md`
