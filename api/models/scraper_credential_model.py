# Database model definitions for scraper credential model.
#
# Session credentials (currently: exported browser cookies) the own-scraper
# needs to reach platforms that require a logged-in session -- LinkedIn
# today, potentially others later. Previously these lived only as a JSON
# file on the VPS filesystem (cookies/linkedin_cookies.json), hand-edited
# over SSH with no record of when it was last refreshed or whether it still
# works. This table is the single source of truth instead; the VPS scraper
# fetches from GET /api/scraping/credentials/<platform> (api-key gated, see
# scraping_routes.py) rather than reading a local file.
#
# One row per (platform, credential_type). `value` holds the raw exported
# credential (e.g. the full cookie-jar array) -- the admin API masks it in
# list responses (api/services/scraper_credential_service.py) so it isn't
# echoed back to the browser by default.
#
# Freshness is tracked two ways, deliberately not just one:
#   - soonest_expiry: passive, free -- the earliest `expirationDate` found
#     in the cookie jar itself at save time. Costs nothing but can be
#     optimistic: platforms (LinkedIn especially) kill sessions early on
#     suspicious activity well before the printed expiry.
#   - last_checked_at / last_check_status: active -- updated from the
#     outcome of the scraper's own real scheduled runs (did it hit a login
#     wall?), not a synthetic ping. Deliberately not a dedicated health-check
#     job hitting the platform purely to self-test, since that's pure extra
#     traffic on a credential we're trying not to get flagged.
from api import db
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB


class ScraperCredential(db.Model):
    __tablename__ = "scraper_credentials"

    id = db.Column(db.Integer, primary_key=True)

    platform = db.Column(db.String(20), nullable=False)
    credential_type = db.Column(db.String(20), nullable=False, default="cookies")
    value = db.Column(JSONB, nullable=False)

    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Passive signal, derived from `value` at write time -- see module docstring.
    soonest_expiry = db.Column(db.DateTime(timezone=True), nullable=True)

    # Active signal, written by the VPS scraper after real usage.
    last_checked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_check_status = db.Column(db.String(20), nullable=True)
    last_check_detail = db.Column(db.Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("platform", "credential_type", name="uq_scraper_credentials_platform_type"),
        CheckConstraint("credential_type IN ('cookies')", name="ck_scraper_credentials_type"),
        CheckConstraint(
            "last_check_status IS NULL OR last_check_status IN ('ok', 'auth_failed', 'error')",
            name="ck_scraper_credentials_check_status",
        ),
    )
