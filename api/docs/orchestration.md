# Scrape Source Orchestration

How the backend chooses between the three scraping sources (Bright Data,
Apify, the in-house scraper), validates what comes back, and records what
happened — the plumbing behind "is our paid data actually available today,
and if not, why".

This is **separate** from `scraping.md`/`SCRAPING_FEATURE.md`, which cover
the existing comment-scraping pipeline (the in-house Instagram scraper
posting comments back through `/api/scraping/*`). This document covers
**profile and post-metric** data — the Bright Data-sourced snapshots that
land in `pages_history` — which today are loaded out-of-band and have no
per-source fallback at all.

## Why

Bright Data is cheap but increasingly returns incomplete profiles/posts.
Apify is consistent but expensive (~$5 to re-scrape one platform's pages
once). The in-house scraper is free but only covers what's actually been
built. Every scrape needs three things this module provides:

1. **A validation check** — did the scrape work, partially work, or fail?
2. **Orchestration** — run the cheap primary source, and only pay for a
   fallback on the specific fields that are actually missing.
3. **An audit trail** — so "how often does this actually work" is a query,
   not a guess, and a client-facing explanation of a gap can be backed by
   real numbers.

## Components

| Piece | File |
|---|---|
| Validation engine | `api/services/scrape_validation_service.py` |
| Source adapters | `api/services/scrape_source_adapters.py` |
| Orchestrator | `api/services/scrape_orchestrator_service.py` |
| Audit log model/repo | `api/models/scrape_attempt_model.py`, `api/repositories/scrape_attempt_repository.py` |
| Reporting | `api/services/orchestration_report_service.py` |
| Admin endpoints | `GET /api/admin/orchestration/{summary,daily,attempts}` |

### Validation

`ScrapeValidationService.validate_profile_snapshot(platform, data)` and
`.validate_posts_snapshot(platform, posts)` check a raw scraped snapshot
against a per-platform field schema and return one of three verdicts:

- **complete** — nothing tracked is missing.
- **partial** — some fields present, some missing (the common case).
- **failed** — nothing usable came back at all (every tracked field null) —
  the signal that the source itself broke/blocked/returned empty, not that
  there's an isolated gap.

The field schema (`PROFILE_FIELD_MAP`, `POSTS_FIELD_MAP`) deliberately
mirrors the JSON key mappings already proven correct in
`PageHistoryRepository._followers_case`/`_description_case`/
`_profile_url_case` and `correction_service.POST_METRIC_PLATFORM_MAP` — if
a platform's scraped shape changes, update it in all three places.

Every non-`complete` result also carries `recommended_sources`: an
ordered, cheapest-first list of sources worth trying to close the gap
(`ScrapeValidationService.recommend_recovery_sources(platform, domain)`,
backed by the static `RECOVERY_SOURCE_PRIORITY` table). This is the
standalone answer to "how can we get the missing data in a reasonably
cheap method" — it works off a platform/domain alone, so it can be asked
even without a specific failed snapshot in hand, and doesn't require
running the orchestrator. It's a recommendation, not a live capability
check: it says nothing about whether the recommended adapter is actually
configured yet (see Status below) — `ScrapeOrchestratorService` makes that
call itself via each adapter's `supports_platform()`, using whatever
adapter list its caller passes in. Keep `RECOVERY_SOURCE_PRIORITY` in sync
by hand with `OwnScraperAdapter.supported_platforms` as the in-house
scraper gains coverage — the module docstring flags this.

### Orchestration

`ScrapeOrchestratorService.run_profile_scrape(page, primary, fallbacks)`:

1. Calls `primary.fetch_profile(...)`, validates it.
2. If not complete, tries each adapter in `fallbacks` (cheapest first) —
   skipping any that don't support the platform — filling in **only** the
   fields still missing. A fallback never overwrites a value the primary
   source already returned.
3. Stops as soon as the merged snapshot validates as complete.
4. Writes one `pages_history` row (with `source`/`source_meta` recording
   which source contributed which field, and the run's total cost) if
   anything usable came back at all.
5. Writes one `scrape_attempts` audit row regardless of outcome.

One adapter raising never aborts the run — see
`api/services/scrape_source_adapters.py`'s docstring for why the actual
Bright Data/Apify HTTP clients aren't wired in here (no credentials or
request/response contract for either service exists in this repo yet).
Each adapter takes an injectable `client` callable; wiring the real HTTP
call is a single, isolated change once that contract exists. Everything
else — the decision logic, the merge, the cost accounting, the audit
trail — is implemented and unit-tested today against fake adapters (see
`api/tests/unit/test_scrape_orchestrator_service.py`).

The in-house scraper adapter (`OwnScraperAdapter`) defaults to supporting
**no platforms** — today's scraper (`instagram-comment-scraper/`) only
collects Instagram comments, not profile/post metrics for any platform.
Extend it with `supported_platforms={...}` and a real client as that
scraper grows.

### Reporting

`GET /api/admin/orchestration/summary?days=7&platform=instagram&domain=profile`
returns, per platform+domain: total attempts, complete/partial/failed
counts, success rate, degraded rate, how often a fallback had to run, and
total fallback cost. `/daily` breaks the same numbers out by day.
`/attempts` lists individual runs (source, what was missing, what the
fallback chain did) for drilling into a specific drop in success rate.

## Status

**Done**: field-level validation with a formal complete/partial/failed
verdict, the fallback-chain orchestrator with cost tracking and per-field
provenance, the `scrape_attempts` audit table + reporting endpoints, and
the `pages_history.source`/`source_meta` columns to know where a snapshot
came from (migration `c8d4e1f6a2b7`).

**Not done / needs product input, not just code**:
- Real Bright Data and Apify HTTP clients (no credentials/contract in this
  repo — see the adapter file's `# TODO(real-client)` markers).
- A cron/scheduler actually calling `run_profile_scrape`/a `run_posts_scrape`
  equivalent per page — right now this is a callable library, not a
  running job. `run_posts_scrape` itself (the `run_profile_scrape`
  equivalent for the posts domain) hasn't been written yet either.
- Deciding real per-field routing policy (which fields the in-house
  scraper should attempt before Apify, once it supports more than
  Instagram comments) — currently that's just "whatever's in the
  `fallbacks` list you pass in, in order."
- Client-facing communication of degraded data (an actual banner/email/SLA
  page) — the `/orchestration/summary` numbers are the raw material for
  that, but nothing renders them to a customer yet, only to admins.
- Backfilling `source` on historical `pages_history` rows (left NULL —
  "unknown/pre-orchestration" — on purpose, not guessed).
