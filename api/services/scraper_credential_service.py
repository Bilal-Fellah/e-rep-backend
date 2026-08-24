# Service layer for managing scraper session credentials (currently:
# exported browser cookies) through the admin API, and serving them to the
# VPS own-scraper. See api/models/scraper_credential_model.py for why this
# table exists instead of a file on the VPS.
from datetime import datetime, timezone

from api.repositories.scraper_credential_repository import ScraperCredentialRepository
from api.utils.logging_utils import instrument_service_class

SUPPORTED_PLATFORMS = ("linkedin", "tiktok")
SUPPORTED_CREDENTIAL_TYPES = ("cookies",)
CHECK_STATUSES = ("ok", "auth_failed", "error")

# The cookie(s) that actually gate the session, per platform -- not every
# cookie in an export. A jar typically also carries short-lived infra/
# analytics cookies (LinkedIn's __cf_bm, lidc, _uetvid, ...) that legitimately
# expire within hours by design; taking the minimum expirationDate across the
# *whole* jar would make soonest_expiry read "expired" within hours of every
# fresh export, regardless of whether the session itself is still good.
# TikTok's pair mirrors its own is_logged_in() check (tiktok_scraper/auth.py:
# `cookies.get("sessionid") or cookies.get("sid_tt")`) -- either one being
# valid is enough to be logged in, but taking the soonest of both here is a
# reasonable, simple signal for an admin-facing expiry badge.
AUTH_COOKIE_NAMES_BY_PLATFORM = {
    "linkedin": ("li_at",),
    "tiktok": ("sessionid", "sid_tt"),
}

# How many days out an expiring credential should start showing yellow/red
# in the admin UI.
EXPIRY_WARNING_DAYS = 14


class ScraperCredentialError(ValueError):
    """Raised for invalid platform/credential_type/value on this surface."""


@instrument_service_class
class ScraperCredentialService:
    @staticmethod
    def _validate_platform(platform: str) -> None:
        if platform not in SUPPORTED_PLATFORMS:
            raise ScraperCredentialError(
                f"Unsupported platform '{platform}' (only {', '.join(SUPPORTED_PLATFORMS)} today)."
            )

    @staticmethod
    def _validate_credential_type(credential_type: str) -> None:
        if credential_type not in SUPPORTED_CREDENTIAL_TYPES:
            raise ScraperCredentialError(
                f"Unsupported credential_type '{credential_type}' "
                f"(only {', '.join(SUPPORTED_CREDENTIAL_TYPES)} today)."
            )

    @staticmethod
    def _soonest_expiry(value, platform: str) -> datetime | None:
        """Earliest `expirationDate` (epoch seconds, browser cookie-export
        convention) among the cookie(s) that actually gate the session for
        `platform` -- see AUTH_COOKIE_NAMES_BY_PLATFORM. Falls back to every
        cookie in the jar only when the platform has no known auth-cookie
        list, since that's still better than no signal at all."""
        if not isinstance(value, list):
            return None
        auth_names = AUTH_COOKIE_NAMES_BY_PLATFORM.get(platform)
        epochs = []
        for cookie in value:
            if not isinstance(cookie, dict):
                continue
            if auth_names and cookie.get("name") not in auth_names:
                continue
            exp = cookie.get("expirationDate")
            if exp is None:
                continue
            try:
                epochs.append(float(exp))
            except (TypeError, ValueError):
                continue
        if not epochs:
            return None
        return datetime.fromtimestamp(min(epochs), tz=timezone.utc)

    @staticmethod
    def _serialize_masked(row) -> dict:
        soonest = row.soonest_expiry
        now = datetime.now(timezone.utc)
        expiry_state = None
        if soonest is not None:
            # SQLite (tests) round-trips DateTime(timezone=True) as naive
            # even though it was written as UTC-aware; Postgres doesn't have
            # this quirk, but normalize either way rather than assume.
            if soonest.tzinfo is None:
                soonest = soonest.replace(tzinfo=timezone.utc)
            days_left = (soonest - now).total_seconds() / 86400
            if days_left < 0:
                expiry_state = "expired"
            elif days_left <= EXPIRY_WARNING_DAYS:
                expiry_state = "expiring_soon"
            else:
                expiry_state = "ok"
        return {
            "platform": row.platform,
            "credential_type": row.credential_type,
            "cookie_count": len(row.value) if isinstance(row.value, list) else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "updated_by": row.updated_by,
            "soonest_expiry": soonest.isoformat() if soonest else None,
            "expiry_state": expiry_state,
            "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
            "last_check_status": row.last_check_status,
            "last_check_detail": row.last_check_detail,
        }

    @staticmethod
    def list_masked() -> list[dict]:
        """For the admin UI: status/expiry per platform, never the raw
        cookie values."""
        return [
            ScraperCredentialService._serialize_masked(row)
            for row in ScraperCredentialRepository.list_all()
        ]

    @staticmethod
    def upsert(platform: str, value, credential_type: str = "cookies", updated_by: int | None = None) -> dict:
        ScraperCredentialService._validate_platform(platform)
        ScraperCredentialService._validate_credential_type(credential_type)
        if not isinstance(value, list) or not value:
            raise ScraperCredentialError("value must be a non-empty list of cookie objects.")

        soonest_expiry = ScraperCredentialService._soonest_expiry(value, platform)
        row = ScraperCredentialRepository.upsert(
            platform=platform,
            credential_type=credential_type,
            value=value,
            soonest_expiry=soonest_expiry,
            updated_by=updated_by,
        )
        return ScraperCredentialService._serialize_masked(row)

    @staticmethod
    def get_raw_for_scraper(platform: str, credential_type: str = "cookies"):
        """VPS-facing: the actual cookie jar, for the scraper to write to
        its cookies file / load into the browser session. Never exposed
        through the admin-facing routes."""
        ScraperCredentialService._validate_platform(platform)
        ScraperCredentialService._validate_credential_type(credential_type)
        row = ScraperCredentialRepository.get(platform, credential_type)
        if row is None:
            raise ScraperCredentialError(
                f"No '{credential_type}' credential stored for platform '{platform}' yet."
            )
        return row.value

    @staticmethod
    def report_check(
        platform: str, status: str, detail: str | None = None, credential_type: str = "cookies"
    ) -> dict:
        """VPS-facing: record the outcome of the scraper's own real run
        against this platform -- the active freshness signal. See module
        docstring on api/models/scraper_credential_model.py for why this
        isn't a separate synthetic health check."""
        ScraperCredentialService._validate_platform(platform)
        ScraperCredentialService._validate_credential_type(credential_type)
        if status not in CHECK_STATUSES:
            raise ScraperCredentialError(f"status must be one of {CHECK_STATUSES}.")

        row = ScraperCredentialRepository.report_check(
            platform=platform,
            credential_type=credential_type,
            status=status,
            detail=detail,
            checked_at=datetime.now(timezone.utc),
        )
        if row is None:
            raise ScraperCredentialError(
                f"No '{credential_type}' credential stored for platform '{platform}' to report against."
            )
        return ScraperCredentialService._serialize_masked(row)
