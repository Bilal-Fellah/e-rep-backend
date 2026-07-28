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

## Local development auth bypass

Erup's `dev_skip` (localStorage, `NODE_ENV=development` only) makes the client
render as a signed-in admin, but it sends no credential. Every `@require_role`
route therefore answered **401**, and the ranking routes — which read the role
via `current_user_role()` rather than failing closed — treated the caller as
anonymous and applied the free tier: **403** on any period outside
`FREE_PERIODS`, and the top-10 cap on everything else.

To close that gap locally, the backend accepts a bypass header:

```bash
# .env on a dev machine only
FLASK_ENV=development
DEV_AUTH_BYPASS=1
DEV_AUTH_USER_ID=1        # optional; must be a real user id — see below
DEV_AUTH_ROLE=admin       # optional; defaults to admin
```

```
X-Dev-Auth: 1   ->  request is treated as {role: DEV_AUTH_ROLE, user_id: DEV_AUTH_USER_ID}
```

**Both** switches are required. `FLASK_ENV` alone is deliberately not enough
because it *defaults* to `development`, so a deployment that simply forgot to
set it would otherwise arm the bypass; `DEV_AUTH_BYPASS` is the explicit opt-in.
With either missing, the header is ignored entirely and the normal JWT path
runs. When it is armed, `create_app()` logs a warning at startup.

`X-Dev-Auth` is listed in the CORS `allow_headers` so the preflight from
`localhost:3000` succeeds. Listing the header name is inert on its own — the
gating above is what actually enables anything.

**`DEV_AUTH_USER_ID` must point at a real local user** for routes that write
rows keyed to one (notes carry an `author_id` foreign key). Bypassing auth does
not create the user; those routes will still fail, on the FK rather than on
auth.

Implementation: `dev_bypass_armed()` / `_dev_bypass_payload()` in
`api/utils/permissions.py`, checked at the top of
`extract_and_validate_token()` — so both `@require_role` and
`current_user_role()` honour it from one place.
