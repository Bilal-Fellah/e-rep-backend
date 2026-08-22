# Business logic for the admin "Data Integrity" report — a read-only
# picture of how much scraped data is missing, so an admin knows where to
# point the Data Corrections tool instead of guessing.
#
# Deliberately read-only: this composes the null-rate queries already
# defined on PageHistoryRepository/PostRepository, it never writes.
from api.repositories.page_history_repository import PageHistoryRepository
from api.repositories.post_repository import PostRepository
from api.services.correction_service import POST_METRIC_PLATFORM_MAP
from api.utils.datetime_utils import iso_utc
from api.utils.logging_utils import instrument_service_class


def _platform_tracks(platform: str, metric: str) -> bool:
    spec = POST_METRIC_PLATFORM_MAP.get(platform)
    return bool(spec) and metric in spec.get("metrics", {})


def _truncate(text, length=140):
    if text is None:
        return None
    text = str(text)
    return text if len(text) <= length else f"{text[: length - 1]}…"


@instrument_service_class
class DataIntegrityService:
    @staticmethod
    def get_summary():
        profile_rows = PageHistoryRepository.get_profile_integrity_by_platform()
        profile_samples = PageHistoryRepository.get_profile_integrity_samples(limit=5)
        post_rows = PostRepository.get_metric_integrity_by_platform()
        post_samples = PostRepository.get_metric_integrity_samples(limit=5)

        return {
            "profile_snapshots": {
                "by_platform": [
                    {
                        "platform": row.platform,
                        "total": int(row.total),
                        "null_followers": int(row.null_followers or 0),
                    }
                    for row in profile_rows
                ],
                "sample_gaps": [
                    {
                        "correction_target_id": str(row.id),
                        "platform": row.platform,
                        "page_name": row.page_name,
                        "page_link": row.page_link,
                        "recorded_at": iso_utc(row.recorded_at),
                        # The rest of what this snapshot *did* capture —
                        # the actual signal for judging whether this is a
                        # real scrape failure (everything empty) or an
                        # isolated gap (bio/photo present, just no count).
                        # followers is always null here (that's the filter),
                        # not repeated as its own field.
                        "biography": _truncate(row.biography),
                        "profile_image": row.profile_image,
                    }
                    for row in profile_samples
                ],
            },
            "posts": {
                "by_platform": [
                    {
                        "platform": row.platform,
                        "total": int(row.total),
                        "null_likes": int(row.null_likes or 0),
                        "null_comments": int(row.null_comments or 0),
                        # A platform that never tracks shares (e.g.
                        # instagram) reports every row's shares as SQL
                        # NULL — that's not a data gap, it's the schema,
                        # so it's surfaced separately rather than as a
                        # "null_shares" count that would always be 100%.
                        "shares_tracked": _platform_tracks(row.platform, "shares"),
                        "null_shares": int(row.null_shares or 0) if _platform_tracks(row.platform, "shares") else None,
                    }
                    for row in post_rows
                ],
                "sample_gaps": [
                    {
                        "correction_target_id": f"{row.page_history_id}:{row.post_id}",
                        "platform": row.platform,
                        "page_name": row.page_name,
                        "recorded_at": iso_utc(row.recorded_at),
                        "missing_fields": [
                            name
                            for name, val in (("likes", row.likes), ("comments", row.comments))
                            if val is None
                        ],
                        # The actual post — a live link to compare against
                        # the real numbers, plus every metric this snapshot
                        # captured (nulls included) so a wrong-but-present
                        # value is visible too, not just a missing one.
                        "url": row.url,
                        "caption": _truncate(row.caption),
                        "likes": row.likes,
                        "comments": row.comments,
                        "shares": row.shares if _platform_tracks(row.platform, "shares") else None,
                        "shares_tracked": _platform_tracks(row.platform, "shares"),
                    }
                    for row in post_samples
                ],
            },
        }

    @staticmethod
    def get_daily(days: int = 14):
        days = max(1, min(int(days), 90))
        profile_rows = PageHistoryRepository.get_profile_integrity_daily(days=days)
        post_rows = PostRepository.get_metric_integrity_daily(days=days)

        return {
            "days": days,
            "profile_snapshots": [
                {
                    "date": str(row.day),
                    "platform": row.platform,
                    "total": int(row.total),
                    "null_followers": int(row.null_followers or 0),
                }
                for row in profile_rows
            ],
            "posts": [
                {
                    "date": str(row.day),
                    "platform": row.platform,
                    "total": int(row.total),
                    "null_likes": int(row.null_likes or 0),
                    "null_comments": int(row.null_comments or 0),
                    "shares_tracked": _platform_tracks(row.platform, "shares"),
                    "null_shares": int(row.null_shares or 0) if _platform_tracks(row.platform, "shares") else None,
                }
                for row in post_rows
            ],
        }
