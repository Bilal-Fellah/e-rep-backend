# Scraping Health API

Per-day delivery for each collection source, and comment coverage measured
against Bright Data's own per-post count.

All routes are prefixed with `/api/admin`, JWT auth, role `admin`. Read-only.

Backed by `api/services/scraping_health_service.py`.

---

## Why this is separate from `/scraping`

`/scraping` is the operational view: sessions, what ran, what's queued. This
one asks a different question — **what did the data look like once it
landed, and is any of it missing.**

The split that makes it useful is by *source*. Two systems feed
`pages_history`, and they fail in opposite ways:

- **our own scraper** loses its browser session and then collects nothing,
  while still exiting cleanly
- **Bright Data** keeps delivering well-formed payloads that simply have no
  engagement fields in them

A combined number hides both. Every table here is split by `source`.

---

## `GET /api/admin/scraping-health/daily`

Query: `days` (default 14, max 90).

```json
{
  "days": 14,
  "brightdata": [
    { "date": "2026-09-03", "platform": "facebook", "rows": 845,
      "errors": 5, "no_followers": 5, "no_posts": 5,
      "no_likes": 5, "no_comments": 5, "usable_pct": 99.4 }
  ],
  "brightdata_errors": [ { "error": "404 Not Found", "count": 300 } ],
  "own_profile":  [ { "date": "2026-08-28", "platform": "instagram",
                      "attempted": 98, "inserted": 97, "insert_pct": 99.0 } ],
  "own_comments": [ { "date": "2026-09-04", "platform": "tiktok",
                      "comments": 142, "posts": 5, "sessions": 1 } ],
  "sessions":     [ { "date": "2026-09-04", "total": 7, "completed": 3,
                      "pending": 4, "failed": 0, "empty_completed": 2,
                      "comments_inserted": 142 } ]
}
```

- `no_posts` / `no_likes` / `no_comments` count snapshots where the posts
  array was absent or empty, or the first post carried no engagement field
  under **any** spelling `posts_mv_queries.sql` accepts (the scrapers
  disagree on casing — `likes_count` vs `likesCount` — so a narrower list
  invents failures).
- `usable_pct` is the share of rows that arrived carrying engagement.
- `empty_completed` is the silent-failure shape: a session that finished
  cleanly having collected nothing.

## `GET /api/admin/scraping-health/comment-coverage`

Query: `days` (default 30, max 90).

Two measures, kept separate on purpose:

| | question |
|---|---|
| **reach** | of the posts that have comments and are inside the window, how many did we visit at all? |
| **completeness** | of the posts we visited, how much of each one's comment count did we capture? |

```json
{
  "window_days": 30,
  "platforms": [{
    "platform": "tiktok",
    "in_window": { "posts_with_comments": 35, "posts_touched": 28,
                   "reach_pct": 80.0, "comments_available": 3203,
                   "comments_unseen": 77 },
    "older":     { "posts_with_comments": 2445, "posts_touched": 0,
                   "reach_pct": 0.0, "comments_unseen": 102944 },
    "completeness": { "posts": 96, "ours": 4343, "ours_top_level": 3762,
                      "brightdata": 5100, "coverage_pct": 85.2,
                      "coverage_top_level_pct": 73.8,
                      "posts_complete": 66, "posts_comparable": 96,
                      "complete_pct": 68.4 }
  }]
}
```

### Reading the numbers honestly

**`older` is not a failure.** The comments flow only visits recent posts
(`scraping_start_date_days`, currently 2). Posts outside the window were
never in scope, so they are reported separately and never folded into the
headline. Counting them as misses produces a number like "we've collected
2.6% of all comments", which is arithmetically true and operationally
meaningless.

**`coverage_pct` above 100% is expected, not a bug.** We capture replies
that Bright Data's per-post count excludes, and we accumulate across repeat
visits while their count is a single point in time. `coverage_top_level_pct`
re-runs it counting only top-level comments, which is the closer
like-for-like.

**Each post is compared against the Bright Data snapshot closest in time to
when we scraped it**, not the latest one — otherwise every comment posted
since would be charged against us.

**The window selects which posts are in scope, not which comment rows
count.** A post collected over three days has all of its comments counted
once it qualifies; filtering the rows themselves would compare one day's
rows against the post's full count and report a fake shortfall.

`null` percentages mean there was nothing to divide by — a platform with no
posts in the window, or no Bright Data count to compare against. LinkedIn
and X currently return `null` completeness because no comment has ever been
collected for either.
