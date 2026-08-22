# Orchestrates one scrape across the three sources (Bright Data primary,
# then the cheapest fallback that can plausibly help, then Apify as a last
# resort) and records what happened.
#
# Flow for one page, one domain (profile or posts):
#   1. Call the primary adapter.
#   2. Validate the result (scrape_validation_service.py). If complete,
#      stop — nothing else to do.
#   3. Otherwise, walk the fallback chain in order. Skip any adapter that
#      doesn't support this platform. Call it, but only use it to fill
#      fields that are STILL missing — a fallback source never overwrites
#      a value the primary source already returned, even if the fallback
#      also returned a value for that field. Re-validate after each
#      fallback; stop early once complete.
#   4. Persist one merged pages_history row (skipped entirely if nothing
#      usable came back from any source — see ValidationResult.is_usable).
#   5. Write one ScrapeAttempt audit row either way, so a total failure is
#      just as visible in the reporting as a success.
#
# This intentionally never raises out of `run_profile_scrape` for an
# adapter failure — one source erroring must not take down the others or
# the whole batch run. It can raise for a programming error (unknown
# platform, misconfigured adapter) since those indicate the caller passed
# something wrong, not that a scrape failed.
from api import db
from api.repositories.page_history_repository import PageHistoryRepository
from api.repositories.scrape_attempt_repository import ScrapeAttemptRepository
from api.services.scrape_source_adapters import AdapterNotConfigured
from api.services.scrape_validation_service import ScrapeValidationService
from api.utils.logging_utils import instrument_service_class


class OrchestrationResult:
    def __init__(self, status, data, sources_used, missing_required, missing_optional, total_cost_usd, attempt, pages_history):
        self.status = status
        self.data = data
        self.sources_used = sources_used
        self.missing_required = missing_required
        self.missing_optional = missing_optional
        self.total_cost_usd = total_cost_usd
        self.attempt = attempt
        self.pages_history = pages_history

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "sources_used": self.sources_used,
            "missing_required": self.missing_required,
            "missing_optional": self.missing_optional,
            "total_cost_usd": self.total_cost_usd,
            "attempt_id": getattr(self.attempt, "id", None),
            "pages_history_id": getattr(self.pages_history, "id", None),
        }


def _safe_fetch(adapter, platform: str, page_link: str, method_name: str):
    """Call one adapter, turning "it doesn't support this platform", "it's
    not configured yet", or "it raised" all into (None, error_message) so
    the caller never has to special-case adapter failures."""
    if not adapter.supports_platform(platform):
        return None, None  # not an error — this adapter just opts out
    try:
        fetch = getattr(adapter, method_name)
        return fetch(platform, page_link), None
    except AdapterNotConfigured as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 - one source's failure must not sink the run
        return None, f"{adapter.name} raised: {exc}"


@instrument_service_class
class ScrapeOrchestratorService:
    @staticmethod
    def run_profile_scrape(page, primary, fallbacks: list, persist: bool = True) -> OrchestrationResult:
        """`page` needs `.uuid`, `.platform`, `.link`. `primary` and each
        entry in `fallbacks` are ScrapeSourceAdapter instances, cheapest
        first. Pass `persist=False` to get the decision back without
        touching the DB (used by tests and dry runs)."""
        platform = page.platform
        fields = ScrapeValidationService.profile_field_map(platform)

        primary_data, primary_error = _safe_fetch(primary, platform, page.link, "fetch_profile")
        primary_result = ScrapeValidationService.validate_profile_snapshot(platform, primary_data)

        merged = dict(primary_data or {})
        source_meta = {"contributions": {}, "cost_usd": primary.cost_per_call_usd}
        for logical_name in primary_result.present_fields:
            source_meta["contributions"][logical_name] = primary.name

        fallback_chain_log = []
        result = primary_result
        total_cost = primary.cost_per_call_usd

        for adapter in fallbacks:
            if result.status == "complete":
                break

            still_missing = result.missing_required + result.missing_optional
            fb_data, fb_error = _safe_fetch(adapter, platform, page.link, "fetch_profile")
            fb_result = ScrapeValidationService.validate_profile_snapshot(platform, fb_data)

            filled = []
            if fb_data:
                for logical_name in still_missing:
                    json_key = fields.get(logical_name)
                    if json_key and merged.get(json_key) is None and fb_data.get(json_key) is not None:
                        merged[json_key] = fb_data[json_key]
                        source_meta["contributions"][logical_name] = adapter.name
                        filled.append(logical_name)

            if filled or fb_data is not None:
                total_cost += adapter.cost_per_call_usd

            fallback_chain_log.append(
                {
                    "source": adapter.name,
                    "status": fb_result.status,
                    "filled_fields": filled,
                    "cost_usd": adapter.cost_per_call_usd,
                    "error": fb_error,
                }
            )

            result = ScrapeValidationService.validate_profile_snapshot(platform, merged)

        source_meta["cost_usd"] = total_cost
        sources_used = ([primary.name] if primary_result.present_fields else []) + [
            entry["source"] for entry in fallback_chain_log if entry["filled_fields"]
        ]

        pages_history = None
        if persist and result.is_usable:
            pages_history = PageHistoryRepository.create(
                page_id=page.uuid,
                data=merged,
                source=sources_used[-1] if sources_used else primary.name,
                source_meta=source_meta,
                commit=False,
            )

        attempt = None
        if persist:
            attempt = ScrapeAttemptRepository.create(
                page_id=page.uuid,
                platform=platform,
                domain="profile",
                primary_source=primary.name,
                primary_status=primary_result.status,
                primary_missing_fields=primary_result.missing_required + primary_result.missing_optional,
                fallback_chain=fallback_chain_log,
                final_status=result.status,
                final_missing_fields=result.missing_required + result.missing_optional,
                total_cost_usd=total_cost,
                pages_history_id=pages_history.id if pages_history else None,
                error_message=primary_error if result.status == "failed" else None,
                commit=False,
            )
            db.session.commit()

        return OrchestrationResult(
            status=result.status,
            data=merged if result.is_usable else None,
            sources_used=sources_used,
            missing_required=result.missing_required,
            missing_optional=result.missing_optional,
            total_cost_usd=total_cost,
            attempt=attempt,
            pages_history=pages_history,
        )
