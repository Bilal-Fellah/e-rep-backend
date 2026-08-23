# Data-access methods for scraper credential repository.
from api.models.scraper_credential_model import ScraperCredential, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class ScraperCredentialRepository:
    """Repository for scraper_credentials database operations."""

    @staticmethod
    def get(platform: str, credential_type: str = "cookies") -> ScraperCredential | None:
        return ScraperCredential.query.filter_by(
            platform=platform, credential_type=credential_type
        ).first()

    @staticmethod
    def list_all() -> list[ScraperCredential]:
        return ScraperCredential.query.order_by(ScraperCredential.platform).all()

    @staticmethod
    def upsert(
        platform: str,
        credential_type: str,
        value,
        soonest_expiry,
        updated_by: int | None,
        commit: bool = True,
    ) -> ScraperCredential:
        """Create or replace the stored credential for (platform, credential_type).

        A full replace, not a merge -- the caller always pastes the complete
        fresh export, so there is nothing to merge field-by-field."""
        row = ScraperCredentialRepository.get(platform, credential_type)
        if row is None:
            row = ScraperCredential(platform=platform, credential_type=credential_type)
            db.session.add(row)
        row.value = value
        row.soonest_expiry = soonest_expiry
        row.updated_by = updated_by
        # A freshly-pasted credential is presumed good until real usage says
        # otherwise -- clear any stale failure status from the credential it
        # replaced rather than carrying it forward.
        row.last_checked_at = None
        row.last_check_status = None
        row.last_check_detail = None
        if commit:
            db.session.commit()
        return row

    @staticmethod
    def report_check(
        platform: str,
        credential_type: str,
        status: str,
        detail: str | None,
        checked_at,
        commit: bool = True,
    ) -> ScraperCredential | None:
        row = ScraperCredentialRepository.get(platform, credential_type)
        if row is None:
            return None
        row.last_checked_at = checked_at
        row.last_check_status = status
        row.last_check_detail = detail
        if commit:
            db.session.commit()
        return row
