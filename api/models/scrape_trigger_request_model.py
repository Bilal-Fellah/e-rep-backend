# Database model definitions for scrape trigger request model.
#
# A small queue table letting an admin fire a manual own-scraper run
# (profile or comments, for one platform) from Brendex Admin, without
# waiting for the next scheduled systemd timer. The backend never reaches
# into the VPS directly -- it only writes a "pending" row here. A poller on
# the VPS (trigger_watcher.py, see api/docs) claims the oldest pending row
# via GET /api/scraping/trigger-requests/next (api-key gated,
# scraping_routes.py), runs the matching systemd service, and reports the
# outcome back via POST .../report. Same poll-the-backend shape already
# used for posts and credentials -- no new privileges needed anywhere.
#
# Deliberately does NOT cover Bright Data or Apify: both are external,
# quota/cost-metered services that stay trigger-by-hand-on-the-VPS (Apify
# explicitly so, per standing instruction) rather than a button anyone with
# admin access can click. See ScrapeTriggerService.TRIGGERABLE for exactly
# which (platform, mode) pairs are accepted.
from api import db
from sqlalchemy import CheckConstraint


class ScrapeTriggerRequest(db.Model):
    __tablename__ = "scrape_trigger_requests"

    id = db.Column(db.Integer, primary_key=True)

    platform = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(20), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="pending")

    requested_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Free-text outcome: systemd Result/ExecMainStatus on success, or an
    # error message (e.g. "no service mapped for x/y") on failure.
    detail = db.Column(db.Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed')",
            name="ck_scrape_trigger_requests_status",
        ),
    )
