import uuid
from types import SimpleNamespace

from api.services.scrape_orchestrator_service import ScrapeOrchestratorService
from api.services.scrape_source_adapters import (
    AdapterNotConfigured,
    ScrapeSourceAdapter,
)


class FakeAdapter(ScrapeSourceAdapter):
    """Returns a fixed profile dict (or raises) without touching the
    network — the orchestrator only depends on the adapter interface, so a
    fake is enough to exercise every branch of the decision logic."""

    def __init__(self, name, profile=None, cost=0.0, platforms=None, raises=None):
        self.name = name
        self.cost_per_call_usd = cost
        self._profile = profile
        self._platforms = platforms
        self._raises = raises
        self.calls = []

    def supports_platform(self, platform: str) -> bool:
        return self._platforms is None or platform in self._platforms

    def fetch_profile(self, platform: str, page_link: str) -> dict | None:
        self.calls.append((platform, page_link))
        if self._raises:
            raise self._raises
        return self._profile


def make_page(platform="instagram", link="https://instagram.com/x"):
    return SimpleNamespace(uuid=uuid.uuid4(), platform=platform, link=link)


def test_primary_complete_short_circuits_fallbacks():
    primary = FakeAdapter("brightdata", {"followers": 100, "biography": "b", "profile_image_link": "u"})
    fallback = FakeAdapter("own_scraper", {"followers": 999})

    result = ScrapeOrchestratorService.run_profile_scrape(make_page(), primary, [fallback], persist=False)

    assert result.status == "complete"
    assert result.data["followers"] == 100  # fallback never called, primary value kept
    assert fallback.calls == []
    assert result.sources_used == ["brightdata"]


def test_fallback_fills_only_missing_fields_without_overwriting_primary():
    primary = FakeAdapter("brightdata", {"followers": 100})  # missing bio + image
    fallback = FakeAdapter(
        "own_scraper", {"followers": 999, "biography": "filled-in", "profile_image_link": "u"}
    )

    result = ScrapeOrchestratorService.run_profile_scrape(make_page(), primary, [fallback], persist=False)

    assert result.status == "complete"
    assert result.data["followers"] == 100  # primary value untouched
    assert result.data["biography"] == "filled-in"  # fallback filled the gap
    assert "own_scraper" in result.sources_used


def test_fallback_that_does_not_support_platform_is_skipped():
    primary = FakeAdapter("brightdata", {})  # total failure
    fallback = FakeAdapter("own_scraper", {"followers": 1}, platforms={"tiktok"})

    result = ScrapeOrchestratorService.run_profile_scrape(
        make_page(platform="instagram"), primary, [fallback], persist=False
    )

    assert fallback.calls == []
    assert result.status == "failed"


def test_all_sources_fail_yields_failed_status_and_no_data():
    primary = FakeAdapter("brightdata", None)
    fallback = FakeAdapter("apify", None, cost=0.5)

    result = ScrapeOrchestratorService.run_profile_scrape(make_page(), primary, [fallback], persist=False)

    assert result.status == "failed"
    assert result.data is None
    assert result.sources_used == []


def test_adapter_exception_does_not_crash_the_run():
    primary = FakeAdapter("brightdata", raises=RuntimeError("boom"))
    fallback = FakeAdapter("own_scraper", {"followers": 5})

    result = ScrapeOrchestratorService.run_profile_scrape(make_page(), primary, [fallback], persist=False)

    # Primary blew up but the fallback still ran and produced a usable,
    # if partial, snapshot.
    assert result.status in ("partial", "complete")
    assert result.data["followers"] == 5


def test_unconfigured_adapter_is_treated_as_a_normal_failure_not_a_crash():
    class UnconfiguredAdapter(ScrapeSourceAdapter):
        name = "brightdata"

        def fetch_profile(self, platform, page_link):
            raise AdapterNotConfigured("no client wired")

    result = ScrapeOrchestratorService.run_profile_scrape(
        make_page(), UnconfiguredAdapter(), [], persist=False
    )
    assert result.status == "failed"


def test_cost_accumulates_only_for_fallbacks_actually_invoked():
    primary = FakeAdapter("brightdata", {"followers": 1, "biography": "b", "profile_image_link": "u"}, cost=0.0)
    unused_fallback = FakeAdapter("apify", {"followers": 2}, cost=0.5)

    result = ScrapeOrchestratorService.run_profile_scrape(
        make_page(), primary, [unused_fallback], persist=False
    )

    assert result.total_cost_usd == 0.0
    assert unused_fallback.calls == []  # primary was already complete


# ── Persistence path ──────────────────────────────────────────────────────
# Follows the same monkeypatched-fake-session style as
# api/tests/integration/test_repos.py rather than hitting the shared
# session-scoped test DB, so this suite can't leak committed rows into
# other tests that share it.

class FakePageHistoryRepository:
    def __init__(self):
        self.created_with = None

    def create(self, page_id, data, source=None, source_meta=None, commit=True):
        self.created_with = {"page_id": page_id, "data": data, "source": source, "source_meta": source_meta}
        return SimpleNamespace(id=101, page_id=page_id, data=data, source=source, source_meta=source_meta)


class FakeScrapeAttemptRepository:
    def __init__(self):
        self.created_with = None

    def create(self, **kwargs):
        self.created_with = kwargs
        return SimpleNamespace(id=55, **kwargs)


def test_run_persists_pages_history_and_scrape_attempt(monkeypatch):
    fake_ph_repo = FakePageHistoryRepository()
    fake_attempt_repo = FakeScrapeAttemptRepository()
    monkeypatch.setattr(
        "api.services.scrape_orchestrator_service.PageHistoryRepository", fake_ph_repo
    )
    monkeypatch.setattr(
        "api.services.scrape_orchestrator_service.ScrapeAttemptRepository", fake_attempt_repo
    )
    monkeypatch.setattr(
        "api.services.scrape_orchestrator_service.db", SimpleNamespace(session=SimpleNamespace(commit=lambda: None))
    )

    primary = FakeAdapter("brightdata", {"followers": 100})
    fallback = FakeAdapter("own_scraper", {"followers": 100, "biography": "hi", "profile_image_link": "u"})

    result = ScrapeOrchestratorService.run_profile_scrape(make_page(), primary, [fallback], persist=True)

    assert fake_ph_repo.created_with["source"] == "own_scraper"  # last contributing source
    assert fake_ph_repo.created_with["source_meta"]["contributions"]["followers"] == "brightdata"
    assert fake_ph_repo.created_with["source_meta"]["contributions"]["biography"] == "own_scraper"

    assert fake_attempt_repo.created_with["final_status"] == "complete"
    assert fake_attempt_repo.created_with["primary_status"] == "partial"
    assert fake_attempt_repo.created_with["pages_history_id"] == 101
    assert result.pages_history.id == 101
    assert result.attempt.id == 55


def test_total_failure_writes_no_pages_history_but_still_logs_attempt(monkeypatch):
    fake_ph_repo = FakePageHistoryRepository()
    fake_attempt_repo = FakeScrapeAttemptRepository()
    monkeypatch.setattr(
        "api.services.scrape_orchestrator_service.PageHistoryRepository", fake_ph_repo
    )
    monkeypatch.setattr(
        "api.services.scrape_orchestrator_service.ScrapeAttemptRepository", fake_attempt_repo
    )
    monkeypatch.setattr(
        "api.services.scrape_orchestrator_service.db", SimpleNamespace(session=SimpleNamespace(commit=lambda: None))
    )

    primary = FakeAdapter("brightdata", None)
    result = ScrapeOrchestratorService.run_profile_scrape(make_page(), primary, [], persist=True)

    assert fake_ph_repo.created_with is None  # nothing usable -> no snapshot written
    assert fake_attempt_repo.created_with["final_status"] == "failed"
    assert result.pages_history is None
    assert result.attempt.id == 55
