# Exercises the real SQLAlchemy queries in ScrapeAttemptRepository (case()/
# sum() over the new scrape_attempts table) against the sqlite test DB, and
# the OrchestrationReportService shaping on top of them — the same
# convention DataIntegrityService would use if it had test coverage.
import uuid

from api.models.entity_model import Entity
from api.models.page_model import Page
from api.repositories.scrape_attempt_repository import ScrapeAttemptRepository
from api.services.orchestration_report_service import OrchestrationReportService


def _make_page(db_session, platform="instagram"):
    entity = Entity(name=f"Test {uuid.uuid4()}", type="company")
    db_session.add(entity)
    db_session.flush()
    page = Page(name="p", link=f"https://x/{uuid.uuid4()}", platform=platform, entity_id=entity.id)
    db_session.add(page)
    db_session.flush()
    return page


def test_summary_rates_and_totals(db_session):
    page = _make_page(db_session)

    ScrapeAttemptRepository.create(
        page_id=page.uuid, platform="instagram", domain="profile",
        primary_source="brightdata", primary_status="complete", primary_missing_fields=[],
        fallback_chain=[], final_status="complete", final_missing_fields=[],
        total_cost_usd=0.0, commit=False,
    )
    ScrapeAttemptRepository.create(
        page_id=page.uuid, platform="instagram", domain="profile",
        primary_source="brightdata", primary_status="partial", primary_missing_fields=["followers"],
        fallback_chain=[{"source": "apify", "status": "complete", "filled_fields": ["followers"], "cost_usd": 0.2}],
        final_status="complete", final_missing_fields=[],
        total_cost_usd=0.2, commit=False,
    )
    ScrapeAttemptRepository.create(
        page_id=page.uuid, platform="instagram", domain="profile",
        primary_source="brightdata", primary_status="failed", primary_missing_fields=["followers"],
        fallback_chain=[{"source": "apify", "status": "failed", "filled_fields": [], "cost_usd": 0.0}],
        final_status="failed", final_missing_fields=["followers"],
        total_cost_usd=0.0, commit=False,
    )
    db_session.flush()

    summary = OrchestrationReportService.get_summary(days=7)
    row = next(r for r in summary["by_platform"] if r["platform"] == "instagram" and r["domain"] == "profile")

    assert row["total"] == 3
    assert row["complete"] == 2
    assert row["failed"] == 1
    assert row["success_rate"] == round(2 / 3, 4)
    assert row["fallback_invoked"] == 2  # both non-"complete" primary runs
    assert row["total_cost_usd"] == 0.2

    assert summary["totals"]["total"] == 3
    assert summary["totals"]["complete"] == 2


def test_daily_and_recent_attempts_shapes(db_session):
    page = _make_page(db_session, platform="tiktok")
    attempt = ScrapeAttemptRepository.create(
        page_id=page.uuid, platform="tiktok", domain="posts",
        primary_source="brightdata", primary_status="partial", primary_missing_fields=["comments"],
        fallback_chain=[], final_status="partial", final_missing_fields=["comments"],
        total_cost_usd=0.0, commit=False,
    )
    db_session.flush()

    daily = OrchestrationReportService.get_daily(days=7, platform="tiktok")
    assert daily
    assert daily[0]["platform"] == "tiktok"
    assert daily[0]["partial"] == 1

    recent = OrchestrationReportService.list_recent_attempts(platform="tiktok", limit=10)
    assert any(a["id"] == attempt.id for a in recent)
    found = next(a for a in recent if a["id"] == attempt.id)
    assert found["final_status"] == "partial"
    assert found["primary_missing_fields"] == ["comments"]
