# STATUS (2026-08-24): not wired into production -- see the status note at
# the top of scrape_orchestrator_service.py for why (real Bright Data/Apify
# clients here would need to be async/polling, not the synchronous
# call-and-get-a-dict shape this file assumes). Kept as a tested design,
# not currently instantiated by anything live.
#
# Adapters for the three scraping sources the orchestrator chooses between
# (see api/services/scrape_orchestrator_service.py): Bright Data (primary,
# cheap, sometimes incomplete), Apify (expensive, more consistent, used as
# a fallback), and the in-house scraper (cheapest, but only covers what's
# actually been built — see instagram-comment-scraper/, which today only
# scrapes Instagram comments, not profile/post metrics).
#
# Every adapter exposes the same tiny surface — `supports_platform` and
# `fetch_profile`/`fetch_posts` — so the orchestrator never branches on
# which source it's talking to; it just calls whichever adapters are given
# to it, in order, until validation says the snapshot is complete.
#
# What's deliberately NOT here: real HTTP calls to Bright Data's or
# Apify's API. This repo has no credentials, base URLs, or sample
# request/response payloads for either service checked in anywhere (see
# CLAUDE.md / the "Fix data problems" task notes) — hand-writing a client
# against a guessed contract would silently ship a broken integration
# that's worse than no integration. Each adapter below takes an injectable
# `client` callable instead: pass it a function that does the actual HTTP
# call (however that ends up looking once you have the contract in hand),
# and the adapter does the rest — platform gating, cost accounting, and
# turning "the client raised" into a validation-friendly `None` rather than
# an unhandled crash. Wire the real client in one place
# (see the `# TODO(real-client)` markers) once it exists; everything else
# in the orchestration pipeline already works against these adapters today
# (see the unit tests using fakes).


class AdapterNotConfigured(RuntimeError):
    """Raised by an adapter that has no client wired in yet (as opposed to
    an adapter that legitimately doesn't support a platform, which returns
    False from supports_platform instead of raising)."""


class ScrapeSourceAdapter:
    """Base class every source adapter implements."""

    name: str = "base"
    # Rough marginal cost of one call, in USD. Used only to sum up
    # total_cost_usd on the ScrapeAttempt audit row for reporting — it does
    # not gate whether the orchestrator calls this adapter (the fallback
    # ordering the caller chooses already encodes "cheapest first").
    cost_per_call_usd: float = 0.0

    def supports_platform(self, platform: str) -> bool:  # noqa: D401 - simple predicate
        return True

    def fetch_profile(self, platform: str, page_link: str) -> dict | None:
        """Return a raw profile snapshot dict in the same shape
        PageHistory.data stores for this platform (see PROFILE_FIELD_MAP in
        scrape_validation_service.py), or None if the call produced
        nothing usable."""
        raise NotImplementedError

    def fetch_posts(self, platform: str, page_link: str) -> list | None:
        """Return a list of raw post dicts (already the flat array a
        validator expects — see POSTS_FIELD_MAP), or None."""
        raise NotImplementedError


class BrightDataAdapter(ScrapeSourceAdapter):
    """Primary source: cheapest per-call cost, but known to sometimes
    return partial data and to not support some collection types at all
    (e.g. Facebook reels, per the task brief)."""

    name = "brightdata"
    cost_per_call_usd = 0.0  # baseline/subscription cost, not billed per call

    def __init__(self, client=None):
        # `client(platform, page_link) -> dict | None` for profiles, and a
        # matching `client_posts` for posts. Left unset by default; calling
        # fetch_* without one raises AdapterNotConfigured rather than
        # silently returning None, so a misconfigured orchestrator run
        # fails loudly instead of looking like "Bright Data returned
        # nothing" in the audit log.
        self._client = client
        # TODO(real-client): wire a Bright Data dataset/API client here
        # once the request contract (dataset id, auth, response shape) is
        # available, e.g. self._client = brightdata_client.fetch_profile

    def fetch_profile(self, platform: str, page_link: str) -> dict | None:
        if self._client is None:
            raise AdapterNotConfigured("BrightDataAdapter has no client configured.")
        return self._client(platform, page_link)

    def fetch_posts(self, platform: str, page_link: str) -> list | None:
        if self._client is None:
            raise AdapterNotConfigured("BrightDataAdapter has no client configured.")
        return self._client(platform, page_link)


class ApifyAdapter(ScrapeSourceAdapter):
    """Last-resort fallback: most consistent, but expensive (task brief:
    ~$5 to scrape one platform's pages once) — so it should only ever be
    invoked for the specific pages/fields still missing after Bright Data
    and the own scraper have both had a chance, never as a bulk primary
    source."""

    name = "apify"

    def __init__(self, client=None, cost_per_call_usd: float = 0.0):
        self._client = client
        # No default cost guess baked in on purpose — the brief only gives
        # a *batch* estimate ("~$5 for one full platform pass"), not a
        # reliable per-page number, and reporting a made-up figure would
        # make the cost tracking on ScrapeAttempt actively misleading.
        # Pass the real per-call cost (or an amortized estimate you trust)
        # when constructing this adapter.
        self.cost_per_call_usd = cost_per_call_usd
        # TODO(real-client): wire an Apify actor-run client here once an
        # actor is chosen per platform.

    def fetch_profile(self, platform: str, page_link: str) -> dict | None:
        if self._client is None:
            raise AdapterNotConfigured("ApifyAdapter has no client configured.")
        return self._client(platform, page_link)

    def fetch_posts(self, platform: str, page_link: str) -> list | None:
        if self._client is None:
            raise AdapterNotConfigured("ApifyAdapter has no client configured.")
        return self._client(platform, page_link)


class OwnScraperAdapter(ScrapeSourceAdapter):
    """Cheapest fallback — but only for what's actually been built.
    `supported_platforms` defaults to empty: today's in-house scraper
    (instagram-comment-scraper/) only collects Instagram comments, not
    profile/post metrics for any platform, so out of the box this adapter
    correctly declines every job and the orchestrator falls through to
    Apify. Pass `supported_platforms={"instagram"}` (and a client) once
    profile/post scraping is actually built for a platform."""

    name = "own_scraper"
    cost_per_call_usd = 0.0  # marginal compute cost, effectively free

    def __init__(self, client=None, supported_platforms: frozenset = frozenset()):
        self._client = client
        self.supported_platforms = frozenset(supported_platforms)

    def supports_platform(self, platform: str) -> bool:
        return platform in self.supported_platforms

    def fetch_profile(self, platform: str, page_link: str) -> dict | None:
        if self._client is None:
            raise AdapterNotConfigured("OwnScraperAdapter has no client configured.")
        return self._client(platform, page_link)

    def fetch_posts(self, platform: str, page_link: str) -> list | None:
        if self._client is None:
            raise AdapterNotConfigured("OwnScraperAdapter has no client configured.")
        return self._client(platform, page_link)
