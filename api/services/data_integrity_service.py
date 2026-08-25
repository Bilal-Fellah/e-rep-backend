# Business logic for the admin "Data Integrity" report — a read-only
# picture of how much scraped data is missing, so an admin knows where to
# point the Data Corrections tool instead of guessing.
#
# Deliberately read-only: this composes the null-rate queries already
# defined on PageHistoryRepository/PostRepository, it never writes.
import uuid
from datetime import datetime, timedelta, timezone

from api.repositories.page_history_repository import PageHistoryRepository
from api.repositories.page_repository import PageRepository
from api.repositories.post_repository import PostRepository
from api.services.correction_service import POST_METRIC_PLATFORM_MAP
from api.services.scrape_validation_service import recommend_recovery_sources
from api.utils.datetime_utils import iso_utc
from api.utils.logging_utils import instrument_service_class


def _platform_tracks(platform: str, metric: str) -> bool:
    spec = POST_METRIC_PLATFORM_MAP.get(platform)
    return bool(spec) and metric in spec.get("metrics", {})


def _recommended_sources_for(missing_keys, platform: str) -> list:
    """Cheapest-first sources worth trying for a page's specific set of
    missing keys -- this is the part of the original brief ("how can we
    get the missing data in a reasonably cheap method") that flagging a
    page as failed doesn't answer by itself: knowing something's missing
    isn't the same as knowing what to do about it cheaply.

    `followers` is a profile-domain gap; everything else validate_data_structure
    reports (posts/top_videos/updates and their "(empty)" variants, likes,
    comments) is a posts-domain gap. A page can have both at once, so this
    unions the recommendation for whichever domain(s) actually apply,
    profile first, deduped, order preserved.
    """
    domains = []
    if "followers" in missing_keys:
        domains.append("profile")
    if any(k != "followers" for k in missing_keys):
        domains.append("posts")

    combined = []
    for domain in domains:
        for source in recommend_recovery_sources(platform, domain):
            if source not in combined:
                combined.append(source)
    return combined


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
    def get_validation_failures(platform: str = None, limit: int = 50):
        """
        Live validation-engine report: pages whose most recent scrape (since
        yesterday 10pm UTC) came back with detectable missing data, per
        PageHistoryRepository.validate_data_structure -- the same check that
        backs GET /api/scraping/apify_profile_scraping. This is deliberately
        NOT Apify-specific: it exists so a human can see what the validation
        engine is finding, independent of whether anything downstream
        (Apify, own-scraper, manual correction) ever acts on it. No paid
        retry is triggered by looking at this.

        Args:
            platform: Optional platform filter.
            limit: Cap on how many individual pages to return in `pages`
                   (the platform summary always covers everything found).

        Returns:
            dict: {
                "generated_at": str,
                "window": {"start": str, "end": str},
                "platform_filter": str | None,
                "total_pages_affected": int,
                "by_platform": [{"platform": str, "pages_affected": int, "issues": {issue: count}}],
                "pages": [{"page_id": str, "name": str, "link": str, "platform": str,
                           "entity_id": int, "entity_name": str | None,
                           "missing_keys": list[str],
                           "recommended_sources": list[str],  # cheapest-first, see _recommended_sources_for
                           "last_checked_at": str}]
            }
        """
        failed_rows = PageHistoryRepository.get_failed_pages_for_today()
        if platform:
            failed_rows = [r for r in failed_rows if r["platform"] == platform]

        # A page can have more than one row in the window (e.g. more than
        # one source wrote a snapshot); merge to one entry per page with
        # the union of missing keys and the most recent recorded_at.
        by_page = {}
        for row in failed_rows:
            key = str(row["page_id"])
            entry = by_page.setdefault(
                key, {"platform": row["platform"], "missing_keys": set(), "recorded_at": row["recorded_at"]}
            )
            entry["missing_keys"].update(row["missing_keys"])
            if row["recorded_at"] > entry["recorded_at"]:
                entry["recorded_at"] = row["recorded_at"]

        # page_id keys are plain strings (they came off validate_data_structure's
        # results), but Page.uuid is a UUID-typed column -- pass real
        # uuid.UUID objects rather than relying on a given driver being
        # lenient about a bare string (see ScrapingService.insert_profile_batch
        # for the same fix, and why: SQLite's UUID emulation isn't lenient,
        # this surfaced as a test failure before it could surface elsewhere).
        page_uuids = [uuid.UUID(pid) for pid in by_page.keys()]
        pages_lookup = {
            str(p.uuid): p for p in PageRepository.get_pages_by_ids(page_uuids, platform=platform)
        }

        # get_pages_by_ids only returns pages whose entity has to_scrape=True
        # -- a page_id with no match here belongs to an inactive entity, so
        # drop it rather than reporting an anonymous entry (no name/link/
        # entity to act on) that still counts toward the totals.
        by_page = {pid: entry for pid, entry in by_page.items() if pid in pages_lookup}

        by_platform_counts = {}
        pages_out = []
        for page_id, entry in by_page.items():
            by_platform_counts.setdefault(entry["platform"], {"pages_affected": 0, "issues": {}})
            plat_summary = by_platform_counts[entry["platform"]]
            plat_summary["pages_affected"] += 1
            for issue in entry["missing_keys"]:
                plat_summary["issues"][issue] = plat_summary["issues"].get(issue, 0) + 1

            page = pages_lookup.get(page_id)
            pages_out.append({
                "page_id": page_id,
                "name": page.name if page else None,
                "link": page.link if page else None,
                "platform": entry["platform"],
                "entity_id": page.entity_id if page else None,
                "entity_name": (page.entity.name if page and page.entity else None),
                "missing_keys": sorted(entry["missing_keys"]),
                "recommended_sources": _recommended_sources_for(entry["missing_keys"], entry["platform"]),
                "last_checked_at": iso_utc(entry["recorded_at"]),
            })

        # Most-recently-checked first, so a fresh failure surfaces before
        # one that's been sitting unaddressed since the start of the window.
        pages_out.sort(key=lambda p: p["last_checked_at"] or "", reverse=True)

        now = datetime.now(timezone.utc)
        yesterday_10pm = (now - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)

        return {
            "generated_at": now.isoformat(),
            "window": {"start": yesterday_10pm.isoformat(), "end": now.isoformat()},
            "platform_filter": platform,
            "total_pages_affected": len(pages_out),
            "by_platform": [
                {"platform": plat, "pages_affected": v["pages_affected"], "issues": v["issues"]}
                for plat, v in sorted(by_platform_counts.items())
            ],
            "pages": pages_out[: max(0, min(limit, 200))],
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
