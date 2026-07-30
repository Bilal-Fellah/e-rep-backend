## Public
only public pages

## Registered (Starter / Free)
- See the top 10 global brands ranked by followers, interactions, and more
- Follower/interactions/top-post data remains on the free restrictions used by the API

## Paid Subscriptions

### Growth
- Ranking limit: up to 30 brands
- Top posts limit: up to 30 posts
- Custom ranges: not allowed
- Premium periods: allowed
- Category scope: one category at a time

### Advanced
- Everything in Growth, plus:
- Ranking limit: up to 50 brands
- Top posts limit: up to 50 posts
- Custom ranges: allowed
- Premium periods: allowed
- Category scope: all categories
- AI/advanced capabilities flagged in `access_rights`:
  - `ai_insights`
  - `ai_recommendations`
  - `comment_sentiment`
  - `influencer_discovery`
  - `ereputation_score`

## Pack policy wiring
Pack policy defaults are derived from `pack_code` (`starter`, `growth`, `advanced`)
and stored in subscription `access_rights`. Admin can still pass explicit
`access_rights` overrides when granting a subscription/preapproval.


---

## Local development auth

There is **no auth bypass**. Every request authenticates through the normal JWT
path, in every environment — `extract_and_validate_token()` has one code path.

Local Erup obtains a real session at `/dev-login` (development builds only; the
route 404s in production). It performs a genuine `POST /api/auth/login` against
whatever `NEXT_PUBLIC_API_URL` points at — including the deployed API, which
already allows `http://localhost:3000` with credentials — and stores the JWT.
Local development therefore runs with a real account and its real role, and
exercises the same entitlement rules as production rather than faking a role
past them.

An earlier `X-Dev-Auth` / `DEV_AUTH_BYPASS` header bypass was removed: it only
worked against a locally-run backend, and its companion `dev_skip` flag rendered
a signed-in admin UI while every data call still 401'd against a deployed API.
