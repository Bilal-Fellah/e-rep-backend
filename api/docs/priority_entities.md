# Priority Clients API

The short list of paying clients whose data gets checked harder than the
fleet-wide Data Integrity report checks anything, plus the ability to fire
an own-scraper run on one client's behalf and then verify it actually
produced data *for that client*.

All routes are prefixed with `/api/admin`, JWT auth, role `admin`.

Backed by `api/services/priority_entity_service.py` and the
`priority_entities` table (`api/models/priority_entity_model.py`).

---

## What this is (and isn't)

**Membership doesn't change scraping.** Putting an entity on the priority
list changes how closely an admin *watches* it. Nothing in the scraping
pipeline reads this table — a priority client is scraped by exactly the
same runs, on the same schedule, as everyone else.

**"Run scrape for this client" is still a platform-wide run.** No scraper
on the VPS can target a single entity today: a run is per `(platform,
mode)` and covers every active page on that platform (see
`ScrapeTriggerService.TRIGGERABLE` and the VPS `trigger_watcher.py`
`SERVICE_MAP`). `POST .../scrape` queues that ordinary run and tags the
request row with the entity it was fired for, so the run can be attributed
and then verified. The verification step is where the per-client precision
actually comes from.

**Verification reads the data, not the run's status.** A run systemd
reported as `done` can still have brought back nothing for a particular
page — an expired login mid-run, a page that now 404s, a page skipped as
not-due. `scrape-check` therefore answers "did *these* pages get new rows
after the moment the run was queued", which is the only form of the
question a client cares about.

---

## Health model

Each page gets `ok` / `warning` / `critical`; an entity takes the worst of
its pages, plus its own blockers.

| Signal | Verdict |
|---|---|
| No snapshot has ever been recorded | `critical` |
| No new snapshot in > `STALE_HOURS` (54h) | `critical` |
| Latest snapshot missing both followers *and* posts (an empty snapshot) | `critical` |
| Snapshots missing on more than half the window's days | `critical` |
| Entity has `to_scrape=false` — it is skipped by every scraper | `critical` |
| Entity has no pages at all | `critical` |
| No new snapshot in > `FRESH_HOURS` (30h) | `warning` |
| Latest snapshot missing some keys (partial scrape) | `warning` |
| Snapshots missing on some days in the window | `warning` |
| Posts missing likes/comments, or no posts collected | `warning` |

The structural completeness check is
`PageHistoryRepository.validate_data_structure` — the same one the retry
pipeline uses to decide a scrape failed, so a page flagged here and a page
flagged there mean the same thing.

---

## Routes

### `GET /api/admin/priority/entities`

Every priority client with health rolled up. Query: `days` (default 7) —
the window for the "did it produce data every day" gap check.

```json
{
  "success": true,
  "data": {
    "entities": [
      {
        "id": 1,
        "entity_id": 42,
        "entity_name": "djezzy",
        "entity_type": "company",
        "to_scrape": true,
        "label": "annual",
        "note": null,
        "created_at": "2026-09-03T10:00:00+00:00",
        "status": "warning",
        "pages_total": 4,
        "pages_ok": 2,
        "pages_warning": 1,
        "pages_critical": 1,
        "issues": ["facebook: No new data for 61h"],
        "last_data_at": "2026-09-03T04:12:00+00:00"
      }
    ]
  }
}
```

### `POST /api/admin/priority/entities`

Body: `{"entity_id": 42, "label": "annual", "note": "..."}` — `label` and
`note` optional, admin-facing only. `201` on success; `400` if the entity
doesn't exist or is already on the list.

### `POST /api/admin/priority/entities/<entity_id>`

Edit `label` / `note`. An empty string clears the field; omitting a field
leaves it unchanged.

### `DELETE /api/admin/priority/entities/<entity_id>`

Removes the entity from the list. Deletes nothing else — not the entity,
not its pages, not its history.

### `GET /api/admin/priority/entities/<entity_id>/check`

The full per-page report. Query: `days` (default 7). Works for any entity,
on the priority list or not (`on_priority_list` says which).

```json
{
  "success": true,
  "data": {
    "entity_id": 42,
    "entity_name": "djezzy",
    "to_scrape": true,
    "on_priority_list": true,
    "status": "warning",
    "days": 7,
    "checked_at": "2026-09-03T12:00:00+00:00",
    "pages": [
      {
        "page_id": "4a706e04-...",
        "page_name": "djezzy on facebook",
        "page_link": "https://facebook.com/djezzy",
        "platform": "facebook",
        "status": "critical",
        "issues": ["No new data for 61h", "Missing data on 2 of the last 7 days"],
        "last_snapshot_at": "2026-09-01T02:00:00+00:00",
        "last_snapshot_source": "own",
        "age_hours": 61.0,
        "missing_keys": [],
        "snapshots_in_window": 5,
        "days_covered": 5,
        "days_expected": 7,
        "posts_total": 120,
        "posts_null_likes": 0,
        "posts_null_comments": 3,
        "last_post_at": "2026-09-01T02:00:00+00:00"
      }
    ],
    "triggerable": [{"platform": "facebook", "mode": "comments"}],
    "recent_runs": [ ... ScrapeTriggerRequest rows fired for this entity ... ]
  }
}
```

`triggerable` is the intersection of the platforms this entity actually has
pages on with `ScrapeTriggerService.TRIGGERABLE` — so the UI never offers a
run that couldn't produce anything for this client.

### `POST /api/admin/priority/entities/<entity_id>/scrape`

Body: `{"platform": "facebook", "mode": "comments"}`. Returns the queued
`ScrapeTriggerRequest` (`201`), now carrying `entity_id`.

`400` if the entity has no page on that platform, or if `(platform, mode)`
isn't in the own-scraper allowlist. Bright Data and Apify are not exposed
here, same as everywhere else.

### `GET /api/admin/priority/entities/<entity_id>/scrape-check?trigger_id=N`

Did run `N` bring back data for this client?

```json
{
  "success": true,
  "data": {
    "entity_id": 42,
    "trigger": { "id": 17, "status": "done", "requested_at": "..." },
    "since": "2026-09-03T12:00:00+00:00",
    "pages_checked": 2,
    "pages_with_new_data": 1,
    "verdict": "partial",
    "pages": [
      {
        "page_id": "4a706e04-...",
        "page_name": "djezzy on facebook",
        "platform": "facebook",
        "new_snapshots": 1,
        "new_posts": 12,
        "scraped": true
      }
    ]
  }
}
```

| `verdict` | Meaning |
|---|---|
| `scraped` | Every page on that platform got new data after the run was queued |
| `partial` | Some pages did, some didn't |
| `waiting` | Nothing yet, but the run is still `pending`/`running` — not a failure |
| `no_data` | The run finished and none of this client's pages got anything |

`no_data` on a run whose status is `done` is the specific case worth
chasing: the scraper exited cleanly and still produced nothing for this
client.
