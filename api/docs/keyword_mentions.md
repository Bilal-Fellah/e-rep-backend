# Tracked Keywords / Mentions API

A client-owned watchlist of up to `TrackedKeywordService.MAX_KEYWORDS_PER_USER`
(currently 3) freeform keywords per user -- not tied to any entity in the
`entities` table. A scheduled VPS pass (`tiktok_scraper`'s keyword-search
mode, on a systemd timer alongside the other scrapers) searches TikTok for
each tracked keyword and reports back any videos it finds.

- Client-facing routes are prefixed with `/api/data`
- Admin (read-only) routes are prefixed with `/api/admin`
- VPS engine routes are prefixed with `/api/scraping`

---

## Authentication

### 1) Client-facing routes (`/api/data/*`)

JWT auth (same as other protected data endpoints):

- `Authorization: Bearer <access_token>`
- Allowed roles: `registered`, `subscribed`, `admin`

### 2) Admin routes (`/api/admin/*`)

JWT auth, role `admin`.

### 3) Engine routes (`/api/scraping/keyword-search/*`)

Service API key:

- `Authorization: Bearer <SCRAPING_API_KEY>`

---

# Client-facing Routes (`/api/data`)

## **GET /api/data/keywords**

List the current user's tracked keywords.

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": 5,
      "user_id": 42,
      "platform": "tiktok",
      "keyword": "brendex",
      "created_at": "2026-08-24T20:00:00"
    }
  ]
}
```

---

## **POST /api/data/keywords**

Add a keyword to the current user's watchlist.

### Request Body

```json
{ "keyword": "brendex", "platform": "tiktok" }
```

`platform` is optional, defaults to `"tiktok"` (the only supported platform today).

### Success Response (201)

```json
{
  "success": true,
  "data": {
    "id": 5,
    "user_id": 42,
    "platform": "tiktok",
    "keyword": "brendex",
    "created_at": "2026-08-24T20:00:00"
  }
}
```

### Error Responses

```json
{ "success": false, "error": "You can track at most 3 keywords -- remove one first" }
```

```json
{ "success": false, "error": "You're already tracking this keyword" }
```

```json
{ "success": false, "error": "platform must be one of ('tiktok',)" }
```

---

## **DELETE /api/data/keywords/{keyword_id}**

Remove a keyword from the current user's watchlist (and its mentions, via
`ON DELETE CASCADE`).

### Success Response (200)

```json
{ "success": true, "data": { "deleted": true } }
```

### Error Responses

```json
{ "success": false, "error": "Keyword not found" }
```

Also returned (not just "doesn't exist") for a keyword owned by a different user.

---

## **GET /api/data/keywords/{keyword_id}/mentions**

List the videos found for one of the current user's tracked keywords, newest
discovered first.

### Query Parameters

- `limit` (optional, default `50`)
- `offset` (optional, default `0`)

### Success Response (200)

```json
{
  "success": true,
  "data": [
    {
      "id": 101,
      "keyword_id": 5,
      "platform": "tiktok",
      "video_id": "7312345678901234567",
      "video_url": "https://www.tiktok.com/@someuser/video/7312345678901234567",
      "author_username": "someuser",
      "caption": "loving my brendex setup",
      "thumbnail_url": "https://p16-sign.tiktokcdn.com/...",
      "like_count": 1200,
      "comment_count": 34,
      "posted_at": "2026-08-20T10:00:00",
      "discovered_at": "2026-08-24T20:05:00"
    }
  ]
}
```

### Error Responses

```json
{ "success": false, "error": "Keyword not found" }
```

---

# Admin Routes (`/api/admin`)

## **GET /api/admin/keywords**

Every client-tracked keyword across all users, with a mention count each.
Read-only -- support/debugging visibility, not a management surface (clients
manage their own via the routes above).

### Query Parameters

- `platform` (optional, default `tiktok`)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "keywords": [
      {
        "id": 5,
        "user_id": 42,
        "platform": "tiktok",
        "keyword": "brendex",
        "created_at": "2026-08-24T20:00:00",
        "mention_count": 7
      }
    ]
  }
}
```

---

# Engine Routes (`/api/scraping/keyword-search`)

For the VPS's scheduled keyword-search pass.

## **GET /api/scraping/keyword-search/keywords**

Every currently tracked keyword for `platform`, across all users. Polled once
per scheduled pass -- no claim/lock semantics, re-searching the same keyword
every pass is expected and cheap to dedupe on the mentions side.

### Query Parameters

- `platform` (required)

### Success Response (200)

```json
{
  "success": true,
  "data": {
    "keywords": [
      { "id": 5, "user_id": 42, "platform": "tiktok", "keyword": "brendex", "created_at": "2026-08-24T20:00:00" }
    ]
  }
}
```

### Error Responses

```json
{ "success": false, "error": "Missing required query parameter: 'platform'." }
```

---

## **POST /api/scraping/keyword-search/keywords/{keyword_id}/mentions**

Report the videos found for one keyword on this pass. Already-recorded
`video_id`s are silently skipped, not duplicated.

### Request Body

```json
{
  "mentions": [
    {
      "video_id": "7312345678901234567",
      "video_url": "https://www.tiktok.com/@someuser/video/7312345678901234567",
      "author_username": "someuser",
      "caption": "loving my brendex setup",
      "thumbnail_url": "https://p16-sign.tiktokcdn.com/...",
      "like_count": 1200,
      "comment_count": 34,
      "posted_at": "2026-08-20T10:00:00"
    }
  ]
}
```

Only `video_id` and `video_url` are required per entry; everything else is
best-effort scrape output and may be omitted.

### Success Response (200)

```json
{ "success": true, "data": { "inserted": 1 } }
```

### Error Responses

```json
{ "success": false, "error": "'mentions' must be an array." }
```

```json
{ "success": false, "error": "No tracked keyword with id 999." }
```
