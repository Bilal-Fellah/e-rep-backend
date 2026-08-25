# Database model definitions for scrape attempt model.
#
# STATUS (2026-08-24): not written to in production -- see the status note
# atop scrape_orchestrator_service.py. This table stays empty until that
# orchestrator (or something else) actually runs; the real, live pipelines
# use pages_history.source/source_meta for provenance instead.
#
# Audit trail for the Bright Data / Apify / own-scraper orchestration flow
# (api/services/scrape_orchestrator_service.py). One row per orchestrated
# scrape (one page, one domain, one run): which source ran first, what it
# was missing, which fallback(s) got invoked to patch the gap, what that
# cost, and where it landed. This is the data the "is our paid data
# actually available today, and if not why" reporting is built on — see
# api/services/orchestration_report_service.py.
#
# Append-only, like data_corrections: written once when the orchestration
# run finishes, never updated afterwards.
from api import db
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID


class ScrapeAttempt(db.Model):
    __tablename__ = "scrape_attempts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    page_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("pages.uuid", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    platform = db.Column(db.String(20), nullable=False)
    # What kind of scrape this was — profile snapshot (followers/bio/image)
    # or the posts/engagement metrics. Kept as one table rather than two so
    # a day's success rate can be queried across both in one place; the
    # domain-specific missing-field vocabulary lives in the JSONB columns,
    # not the schema.
    domain = db.Column(db.String(20), nullable=False)

    started_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    primary_source = db.Column(db.String(20), nullable=False)
    primary_status = db.Column(db.String(20), nullable=False)
    primary_missing_fields = db.Column(JSONB, nullable=True)

    # One entry per fallback adapter actually invoked, in the order tried:
    # [{"source": "own_scraper", "status": "partial", "filled_fields": [...],
    #   "cost_usd": 0.0}, ...]. Empty/NULL means the primary source alone
    # was already complete and no fallback was needed.
    fallback_chain = db.Column(JSONB, nullable=True)

    final_status = db.Column(db.String(20), nullable=False)
    final_missing_fields = db.Column(JSONB, nullable=True)
    total_cost_usd = db.Column(db.Numeric(10, 4), nullable=False, server_default="0")

    # The snapshot this run actually wrote, if any (a "failed" run with no
    # usable data at all writes no pages_history row, so this stays NULL).
    pages_history_id = db.Column(
        db.Integer, db.ForeignKey("pages_history.id", ondelete="SET NULL"), nullable=True
    )
    error_message = db.Column(db.Text, nullable=True)

    __table_args__ = (
        CheckConstraint("domain IN ('profile', 'posts')", name="ck_scrape_attempts_domain"),
        CheckConstraint(
            "primary_status IN ('complete', 'partial', 'failed')",
            name="ck_scrape_attempts_primary_status",
        ),
        CheckConstraint(
            "final_status IN ('complete', 'partial', 'failed')",
            name="ck_scrape_attempts_final_status",
        ),
    )
