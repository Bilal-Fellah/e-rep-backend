# Business logic for validating one scraped snapshot right after it comes
# back from a source (Bright Data / Apify / own scraper) — "did this
# scraping task work, partially work, or fail?"
#
# This is the synchronous counterpart to DataIntegrityService: that service
# reports null rates *after the fact*, across everything already in the DB,
# for an admin to look at. This one is called *inline*, once per scrape, by
# ScrapeOrchestratorService, so the orchestrator can decide whether to stop
# or escalate to a fallback source before anything is written.
#
# The field maps below intentionally mirror two things that already exist
# and are proven correct in production:
#   - PageHistoryRepository._followers_case / _description_case /
#     _profile_url_case (api/repositories/page_history_repository.py)
#   - POST_METRIC_PLATFORM_MAP (api/services/correction_service.py)
# If a platform's scraped JSON shape ever changes, update it in both places
# together — this module does not import the SQL case-builders (they only
# make sense inside a query), so there is no way to enforce that at import
# time, only by convention.
from dataclasses import dataclass, field

from api.utils.logging_utils import instrument_service_class

# platform -> {logical_field: json_key_or_None}. `None` means this platform's
# scraper doesn't capture that field at all (not a gap, a schema fact) —
# e.g. Facebook's pages_history rows don't carry a bio/profile-image key
# today, same as PageHistoryRepository._description_case/_profile_url_case
# simply have no `case()` branch for facebook (so SQL returns NULL, not an
# error).
PROFILE_FIELD_MAP = {
    "instagram": {"followers": "followers", "biography": "biography", "profile_image": "profile_image_link"},
    "facebook": {"followers": "page_followers", "biography": None, "profile_image": None},
    "x": {"followers": "followers", "biography": "biography", "profile_image": "profile_image_link"},
    "tiktok": {"followers": "followers", "biography": "biography", "profile_image": "profile_pic_url"},
    "linkedin": {"followers": "followers", "biography": "about", "profile_image": "logo"},
    "youtube": {"followers": "subscribers", "biography": "Description", "profile_image": "profile_image"},
}

# Only `followers` blocks rankings/paid delivery, so it's the one field that
# can push status to "failed"/"partial" on its own; bio/image are optional
# signal, same distinction DataIntegrityService already draws between its
# null-rate count (followers only) and its "also show whatever we did get"
# sample fields.
PROFILE_REQUIRED = ("followers",)
PROFILE_OPTIONAL = ("biography", "profile_image")

# platform -> {array_key, id_key, required metrics, optional metrics}.
# Mirrors POST_METRIC_PLATFORM_MAP field-for-field; `shares` is only
# "required" to be non-null where the platform tracks it at all (see
# DataIntegrityService._platform_tracks for the read-side equivalent).
POSTS_FIELD_MAP = {
    "instagram": {"array_key": "posts", "id_key": "id", "required": {"likes": "likes", "comments": "comments"}, "optional": {}},
    "linkedin": {
        "array_key": "updates",
        "id_key": "post_id",
        "required": {"likes": "likes_count", "comments": "comments_count"},
        "optional": {},
    },
    "tiktok": {
        "array_key": "top_videos",
        "id_key": "video_id",
        "required": {"likes": "favorites_count", "comments": "commentcount"},
        "optional": {"shares": "share_count"},
    },
    "youtube": {
        "array_key": "top_videos",
        "id_key": "video_id",
        "required": {"likes": "like_count", "comments": "comment_count"},
        "optional": {},
    },
    "x": {
        "array_key": "posts",
        "id_key": "post_id",
        "required": {"likes": "likes", "comments": "replies"},
        "optional": {"shares": "reposts"},
    },
    "facebook": {
        "flat": True,
        "required": {"likes": "likes", "comments": "num_comments"},
        "optional": {"shares": "num_shares"},
    },
}


# Static "what's worth trying next, cheapest first" policy — this answers
# the brief's "how can we get the missing data in a reasonably cheap
# method" question on its own, without having to actually run the
# orchestrator. It is a *recommendation*, not a capability check: it says
# nothing about whether a given adapter is configured/implemented today,
# only which source is worth trying first if it were.
#
# Keep this in sync by hand with what's actually wired in
# scrape_source_adapters.py — in particular OwnScraperAdapter's
# `supported_platforms` default (empty today, since the in-house scraper
# only does Instagram comments, not profile/post data, for any platform
# yet). Once the in-house scraper gains real profile/post coverage for a
# platform, move that platform's entry here to lead with "own_scraper",
# not just wire the adapter — otherwise the recommendation and reality
# drift apart silently.
RECOVERY_SOURCE_PRIORITY = {
    "profile": {
        "instagram": ["own_scraper", "apify"],
        "facebook": ["apify"],
        "x": ["apify"],
        "tiktok": ["apify"],
        "linkedin": ["apify"],
        "youtube": ["apify"],
    },
    "posts": {
        "instagram": ["own_scraper", "apify"],
        "facebook": ["apify"],
        "x": ["apify"],
        "tiktok": ["apify"],
        "linkedin": ["apify"],
        "youtube": ["apify"],
    },
}
# Fallback for a platform this table hasn't been taught about yet: Apify is
# the one source that's supposed to work everywhere, so it's the safe
# default rather than silently recommending nothing.
_DEFAULT_RECOVERY_PRIORITY = ["apify"]


def recommend_recovery_sources(platform: str, domain: str = "profile") -> list:
    """Ordered, cheapest-first list of sources worth trying to fill a gap
    for this platform/domain — independent of any specific scrape result,
    so it can answer "what would we try here" even before anything has
    failed. `ScrapeOrchestratorService` doesn't consult this directly (it
    takes an explicit adapter list from its caller instead, since it also
    needs live adapter instances, not just names) — this is the
    standalone, human/reporting-facing answer to the same question.
    """
    return list(RECOVERY_SOURCE_PRIORITY.get(domain, {}).get(platform, _DEFAULT_RECOVERY_PRIORITY))


@dataclass
class ValidationResult:
    # "complete": nothing tracked is missing.
    # "partial": some tracked fields present, some missing.
    # "failed": nothing usable came back at all (every tracked field, or
    #   every post's every metric, is missing) — the signal that this
    #   wasn't "a gap", the source likely errored/blocked/returned empty.
    status: str
    missing_required: list = field(default_factory=list)
    missing_optional: list = field(default_factory=list)
    present_fields: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    # Cheapest-first sources worth trying to close the gap — empty when
    # status is "complete" (nothing to recover), populated from
    # RECOVERY_SOURCE_PRIORITY otherwise. See recommend_recovery_sources().
    recommended_sources: list = field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """True if this snapshot is worth keeping even if incomplete —
        i.e. anything but a total failure."""
        return self.status != "failed"


class ScrapeValidationError(ValueError):
    """Raised for a platform this module has no field schema for."""


def _profile_fields(platform: str) -> dict:
    fields = PROFILE_FIELD_MAP.get(platform)
    if fields is None:
        raise ScrapeValidationError(f"No profile field schema for platform '{platform}'.")
    return fields


def validate_profile_snapshot(platform: str, data: dict | None) -> ValidationResult:
    """Check one profile snapshot's top-level scraped fields (the same
    shape a Bright Data/Apify/own-scraper adapter returns, and the same
    shape PageHistory.data stores) against what that platform is expected
    to carry."""
    fields = _profile_fields(platform)
    data = data or {}

    missing_required, missing_optional, present = [], [], []
    for logical_name in PROFILE_REQUIRED:
        json_key = fields.get(logical_name)
        if json_key is None:
            continue  # platform doesn't track this field at all — not a gap
        (present if data.get(json_key) is not None else missing_required).append(logical_name)
    for logical_name in PROFILE_OPTIONAL:
        json_key = fields.get(logical_name)
        if json_key is None:
            continue
        (present if data.get(json_key) is not None else missing_optional).append(logical_name)

    if not present and (missing_required or missing_optional):
        status = "failed"
    elif missing_required or missing_optional:
        status = "partial"
    else:
        status = "complete"

    return ValidationResult(
        status=status,
        missing_required=missing_required,
        missing_optional=missing_optional,
        present_fields=present,
        recommended_sources=[] if status == "complete" else recommend_recovery_sources(platform, "profile"),
    )


def validate_posts_snapshot(platform: str, posts: list | None, min_expected_posts: int = 1) -> ValidationResult:
    """Check a batch of scraped posts' engagement metrics. `posts` is the
    already-extracted array (e.g. `data["posts"]` for Instagram, or the
    list of flat Facebook rows for one page) — extracting that array out of
    the raw snapshot is the adapter's job, not this function's, so the same
    validator works regardless of where each platform nests it."""
    spec = POSTS_FIELD_MAP.get(platform)
    if spec is None:
        raise ScrapeValidationError(f"No posts field schema for platform '{platform}'.")
    posts = posts or []

    if len(posts) < min_expected_posts:
        return ValidationResult(
            status="failed" if not posts else "partial",
            missing_required=["posts"],
            detail={"expected_min_posts": min_expected_posts, "got": len(posts)},
            recommended_sources=recommend_recovery_sources(platform, "posts"),
        )

    required = spec["required"]
    optional = spec.get("optional", {})
    total = len(posts)
    missing_counts = {name: 0 for name in list(required) + list(optional)}

    for post in posts:
        for name, json_key in required.items():
            if post.get(json_key) is None:
                missing_counts[name] += 1
        for name, json_key in optional.items():
            if post.get(json_key) is None:
                missing_counts[name] += 1

    missing_required = [name for name in required if missing_counts[name] > 0]
    missing_optional = [name for name in optional if missing_counts[name] > 0]
    present = [name for name in list(required) + list(optional) if missing_counts[name] == 0]

    # Total failure = every post is missing every required metric, i.e.
    # nothing usable came back at all, not just an isolated gap.
    all_required_always_missing = bool(required) and all(
        missing_counts[name] == total for name in required
    )

    if not missing_required and not missing_optional:
        status = "complete"
    elif all_required_always_missing:
        status = "failed"
    else:
        status = "partial"

    return ValidationResult(
        status=status,
        missing_required=missing_required,
        missing_optional=missing_optional,
        present_fields=present,
        detail={"total_posts": total, "missing_counts": missing_counts},
        recommended_sources=[] if status == "complete" else recommend_recovery_sources(platform, "posts"),
    )


@instrument_service_class
class ScrapeValidationService:
    """Thin static-method wrapper so callers use the same
    `Service.method(...)` shape as every other service in this codebase;
    the module-level functions above are the actual implementation and are
    also importable directly for unit tests."""

    ScrapeValidationError = ScrapeValidationError
    ValidationResult = ValidationResult

    @staticmethod
    def validate_profile_snapshot(platform: str, data: dict | None) -> ValidationResult:
        return validate_profile_snapshot(platform, data)

    @staticmethod
    def validate_posts_snapshot(platform: str, posts: list | None, min_expected_posts: int = 1) -> ValidationResult:
        return validate_posts_snapshot(platform, posts, min_expected_posts=min_expected_posts)

    @staticmethod
    def profile_field_map(platform: str) -> dict:
        return _profile_fields(platform)

    @staticmethod
    def recommend_recovery_sources(platform: str, domain: str = "profile") -> list:
        return recommend_recovery_sources(platform, domain)
