# Database model definitions for scraping profile result model.
#
# Same shape/purpose as ScrapingPostResult, for the profile-info flow (see
# api/docs/scraping_profiles.md). One row per (page_id, platform,
# scraping_session_id) attempt — including accounts that turned out to be
# unscrapeable, so they're marked done rather than re-served forever.
#
# `account_id` is carried because the external scraper's client
# (core/api_client.py on the scraper side) always sends one — its comment
# explains it's designed for a future where one real-world account could
# map to more than one `pages` row. Today's schema has no separate accounts
# table and `pages.link` is unique, so `account_id` is always just
# str(page.uuid) in practice; it's stored as sent rather than assumed, so
# nothing here breaks if that ever changes.
from datetime import datetime
from sqlalchemy import inspect
from api import db


class ScrapingProfileResult(db.Model):
    __tablename__ = "scraping_profile_results"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    page_id = db.Column(db.String(36), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    account_id = db.Column(db.String(64), nullable=False)

    scraping_session_id = db.Column(
        db.String(36),
        db.ForeignKey("scraping_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )

    # False for an account that was visited but turned out to be
    # unavailable/unscrapeable (the scraper still reports these so they
    # aren't re-served on every pass) — mirrors comments_count=0 on
    # ScrapingPostResult meaning "scraped, nothing there".
    profile_inserted = db.Column(db.Boolean, nullable=False, default=True)

    scraped_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "page_id", "platform", "scraping_session_id",
            name="uq_scraping_profile_result",
        ),
        db.Index("ix_spfr_page_lookup", "page_id", "platform"),
        db.Index("ix_spfr_scraped_at", "scraped_at"),
        db.Index("ix_spfr_session", "scraping_session_id"),
    )

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
