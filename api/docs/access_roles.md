## Public
only public pages

## Registered
Full Brands rankings
Complete user profile data access
Follower history & comparisons(last month only)
Interactions history & comparisons(last month only)
See Top posts by date and brand(last month only)


## Subscription
Full Brands rankings
Complete user profile data access
Follower history & comparisons
Interactions history & comparisons
Posts timeline analysis
See Top posts by date and brand


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
