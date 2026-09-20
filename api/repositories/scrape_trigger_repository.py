# Data-access methods for scrape trigger request repository.
from api.models.scrape_trigger_request_model import ScrapeTriggerRequest, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class ScrapeTriggerRepository:
    """Repository for scrape_trigger_requests database operations."""

    @staticmethod
    def create(
        platform: str,
        mode: str,
        requested_by: int | None,
        entity_id: int | None = None,
        commit: bool = True,
    ) -> ScrapeTriggerRequest:
        row = ScrapeTriggerRequest(
            platform=platform,
            mode=mode,
            status="pending",
            requested_by=requested_by,
            entity_id=entity_id,
        )
        db.session.add(row)
        if commit:
            db.session.commit()
        return row

    @staticmethod
    def list_for_entity(entity_id: int, limit: int = 20) -> list[ScrapeTriggerRequest]:
        """Manual runs fired from the Priority page for one client, newest
        first -- the per-entity slice of list_recent()."""
        return (
            ScrapeTriggerRequest.query.filter_by(entity_id=entity_id)
            .order_by(ScrapeTriggerRequest.requested_at.desc(), ScrapeTriggerRequest.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_by_id(request_id: int) -> ScrapeTriggerRequest | None:
        return db.session.get(ScrapeTriggerRequest, request_id)

    @staticmethod
    def list_recent(limit: int = 50) -> list[ScrapeTriggerRequest]:
        # Tie-break on id: two requests queued in the same transaction/tick
        # can land on an identical requested_at, and id is monotonic where
        # a timestamp alone isn't fine-grained enough to order them.
        return (
            ScrapeTriggerRequest.query.order_by(
                ScrapeTriggerRequest.requested_at.desc(), ScrapeTriggerRequest.id.desc()
            )
            .limit(limit)
            .all()
        )

    @staticmethod
    def latest_for(platform: str, mode: str) -> ScrapeTriggerRequest | None:
        """Most recent request for one (platform, mode) pair -- e.g. the
        "Run now" status shown on Erup's Keywords page, which only ever
        cares about its own (tiktok, keyword-search) history, not the
        full cross-platform list Brendex Admin's trigger panel shows."""
        return (
            ScrapeTriggerRequest.query.filter_by(platform=platform, mode=mode)
            .order_by(ScrapeTriggerRequest.requested_at.desc(), ScrapeTriggerRequest.id.desc())
            .first()
        )

    @staticmethod
    def claim_next_pending(started_at, commit: bool = True) -> ScrapeTriggerRequest | None:
        """Atomically claim the oldest pending request. `FOR UPDATE SKIP
        LOCKED` so a second concurrent poller -- there shouldn't be one,
        but the VPS watcher could in principle be restarted mid-poll --
        can't grab the same row twice."""
        row = (
            ScrapeTriggerRequest.query.filter_by(status="pending")
            .order_by(ScrapeTriggerRequest.requested_at.asc(), ScrapeTriggerRequest.id.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if row is None:
            return None
        row.status = "running"
        row.started_at = started_at
        if commit:
            db.session.commit()
        return row

    @staticmethod
    def report_result(
        request_id: int, status: str, detail: str | None, finished_at, commit: bool = True
    ) -> ScrapeTriggerRequest | None:
        row = db.session.get(ScrapeTriggerRequest, request_id)
        if row is None:
            return None
        row.status = status
        row.detail = detail
        row.finished_at = finished_at
        if commit:
            db.session.commit()
        return row
