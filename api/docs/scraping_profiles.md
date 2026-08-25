# Scraping Profile-Info API

Counterpart to `scraping.md` (comments) for the own-scraper's *profile*
pass — `core/profile_api_flow.py` on the scraper side (Instagram only
today; see `run_api_docker.sh`'s `MODE=profile` gate).

**Why this exists:** the scraper has called these two endpoints on every
run since it was deployed. They didn't exist. Every call 404'd, silently
(the systemd service still exits 0), so the own-scraper's Instagram
profile pass has never written a row to the database — see the bug
writeup this was built to fix. The contract below was read directly off
the deployed scraper's `core/api_client.py`/`core/profile_api_flow.py`,
not guessed, precisely so it would actually match what's already calling it.

Auth: `Authorization: Bearer {SCRAPING_API_KEY}` (same key as `/posts`/`/comments`).

**Naming note:** while building this, `GET /api/scraping/profiles` turned
out to already exist upstream (`ScrapingService.get_profiles_for_scraping`)
— added independently, with a different response shape (no session
tracking, feeds the Apify fallback pipeline's `apify_profile_scraping`
route instead). The two solve genuinely different problems on what would
otherwise be the same URL, so the fetch route below lives at
`/own_scraper/profiles` instead of claiming plain `/profiles` — see the
route's docstring in `scraping_routes.py` for the full reasoning. Nothing
about `/profiles` or `/apify_profile_scraping` was touched.

---

## GET /api/scraping/own_scraper/profiles

Fetch accounts whose profile info is due for a refresh, and open a
scraping session.

**Query params:** `platform` (required — only `instagram` today),
`start_date`, `recorded_start_date`, `recorded_end_date` (accepted for
client-contract parity; not currently used to filter — a page has no
per-row content date the way a post does, so the only real filter is
"not already handled today").

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "…",
    "profiles": [{"account_id": "<page uuid>", "page_id": "<page uuid>", "url": "https://instagram.com/…"}],
    "count": 12,
    "total_available": 98
  }
}
```
`account_id` and `page_id` are always the same value today — this schema
has no separate "accounts" table (`pages.link` is unique), so there's
nothing else for `account_id` to mean yet. Sent as sent, not assumed —
see `ScrapingProfileResult`'s docstring.

## POST /api/scraping/profile-info

Insert scraped profile records in bulk.

**Request body:**
```json
{
  "session_id": "…",
  "profiles": [
    {
      "page_id": "…", "platform": "instagram", "account_id": "…",
      "followers": 4242, "biography": "…", "profile_image_link": "…",
      "posts": [...], "highlights": [...]
    }
  ],
  "profile_results": [
    {"page_id": "…", "platform": "instagram", "account_id": "…"}
  ]
}
```
`profile_results` lists every account actually visited this batch —
including ones that turned out unscrapeable — so it's marked done and
not re-served forever, exactly like `post_results` on `/comments`.

Each `profiles` entry is written as one new `pages_history` row (`source
= "own_scraper"`), stripped of just the three routing keys
(`page_id`/`platform`/`account_id`) — everything else the scraper
captured is stored as-is, because its field names for Instagram
(`followers`, `biography`, `profile_image_link`) already match what
`PageHistoryRepository`'s case-builders and
`scrape_validation_service.PROFILE_FIELD_MAP` expect. One invalid entry
rejects the whole batch (same behavior as `/comments`) — the scraper
already defensively coerces null/missing fields before sending, expecting
exactly that.

**Response:**
```json
{"success": true, "data": {"session_id": "…", "inserted": 3, "skipped": 0, "total": 3}}
```

## Data model

`scraping_profile_results` (migration `d3f9a7c1e4b5`) — one row per
`(page_id, platform, scraping_session_id)` attempt, `profile_inserted`
distinguishing "scraped and written" from "visited, turned out
unscrapeable" — mirrors `scraping_post_results` exactly.

## What this doesn't do yet

- Not deployed. This is built and tested against the local checkout; the
  live scraper talks to `/home/bilal/e-rep`, a separate deployment this
  work hasn't touched.
- Doesn't distinguish a validation-error batch from a partial success —
  same all-or-nothing behavior `/comments` already has.
- `ScrapingSession.comments_inserted` is left untouched by a profile
  batch (profiles aren't comments) — a profile session's `posts_fetched`
  is really "accounts fetched." A future `kind` column on `ScrapingSession`
  would make that precise instead of just documented here.
