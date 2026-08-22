"""Single source of truth for the `Cache-Control` header on API responses.

Nothing else in the stack sets one: `nginx.conf` is a bare `proxy_pass`, and no
route builds its own headers. That left every response — authenticated rankings,
notes, `/api/auth/me` — going out with no cache directives at all, which lets an
intermediary apply heuristic caching to per-user JSON.

The policy here is deny-by-default: `register_cache_control` installs an
`after_request` hook that stamps `no-store` on anything that hasn't already
declared a policy. A view opts out by wrapping itself in `@cache_public`, which
is only correct for endpoints whose body is identical for every caller.
"""

from functools import wraps

from flask import make_response

# Applies to everything that doesn't opt in. `no-store` (rather than
# `private, no-cache`) also keeps the auth responses that carry `Set-Cookie`
# out of the browser's back/forward cache on shared machines.
PRIVATE_CACHE_CONTROL = "no-store"


def cache_public(max_age, stale_while_revalidate=None):
    """Allow shared caches to serve this view's response for `max_age` seconds.

    Only for endpoints that read no session, no JWT, and no per-user state — the
    directive is `public`, so a CDN or proxy may hand one caller's body to the
    next. flask-cors already emits `Vary: Origin`, so the allowed-origin echo
    stays correctly keyed.

    Non-2xx/3xx responses are left alone and fall through to `no-store`: a cached
    404 from a transient empty-data window would outlive the window itself.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            response = make_response(view(*args, **kwargs))

            if response.status_code >= 400:
                return response

            directives = [
                "public",
                f"max-age={max_age}",
                f"s-maxage={max_age}",
            ]
            if stale_while_revalidate is not None:
                directives.append(f"stale-while-revalidate={stale_while_revalidate}")

            response.headers["Cache-Control"] = ", ".join(directives)
            return response

        return wrapper

    return decorator


def register_cache_control(app):
    """Default every response without an explicit policy to `no-store`."""

    @app.after_request
    def _apply_default_cache_control(response):
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = PRIVATE_CACHE_CONTROL
        return response

    return app
