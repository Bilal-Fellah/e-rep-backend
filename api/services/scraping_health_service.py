# Business logic for the admin "Scraping Health" report.
#
# Answers three questions the existing pages don't:
#
#   1. What did each collection SOURCE deliver, per day? Our own scraper and
#      Bright Data fail in completely different ways -- one loses its login
#      and collects nothing, the other keeps delivering payloads that are
#      structurally fine but carry no engagement -- so a combined number
#      hides both.
#   2. Did the runs actually record their failures? (Historically: no.)
#   3. Are we collecting all the comments that exist, measured against
#      Bright Data's own per-post count as ground truth?
#
# Read-only throughout.
from api.repositories.scraping_health_repository import ScrapingHealthRepository
from api.utils.logging_utils import instrument_service_class

DEFAULT_DAYS = 14
MAX_DAYS = 90

# Default window for the coverage view. Reach is measured against posts
# this recent; completeness against posts we visited this recently (all of
# their comments counted, not just the ones recorded inside the window).
# 30 days rather than the scraper's own 2-day horizon: a shorter window
# leaves so few posts per platform that one partial run swings the figure
# wildly, which reads as a data problem rather than a small sample.
COVERAGE_WINDOW_DAYS = 30


def _pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else None


@instrument_service_class
class ScrapingHealthService:
    @staticmethod
    def _clamp(days: int) -> int:
        try:
            days = int(days)
        except (TypeError, ValueError):
            return DEFAULT_DAYS
        return max(1, min(days, MAX_DAYS))

    @staticmethod
    def daily(days: int = DEFAULT_DAYS) -> dict:
        """Per-day activity for both sources plus session outcomes."""
        days = ScrapingHealthService._clamp(days)
        return {
            "days": days,
            "brightdata": [
                {
                    "date": r.d.isoformat(),
                    "platform": r.platform,
                    "rows": int(r.rows),
                    "errors": int(r.errors),
                    "no_followers": int(r.no_followers),
                    "no_posts": int(r.no_posts),
                    "no_likes": int(r.no_likes),
                    "no_comments": int(r.no_comments),
                    # The share of what arrived that was actually usable.
                    "usable_pct": _pct(int(r.rows) - int(r.no_likes), int(r.rows)),
                }
                for r in ScrapingHealthRepository.brightdata_daily(days)
            ],
            "brightdata_errors": [
                {"error": r.error, "count": int(r.n)}
                for r in ScrapingHealthRepository.brightdata_errors(days)
            ],
            "own_profile": [
                {
                    "date": r.d.isoformat(),
                    "platform": r.platform,
                    "attempted": int(r.attempted),
                    "inserted": int(r.inserted),
                    "insert_pct": _pct(int(r.inserted), int(r.attempted)),
                }
                for r in ScrapingHealthRepository.own_profile_daily(days)
            ],
            "own_comments": [
                {
                    "date": r.d.isoformat(),
                    "platform": r.platform,
                    "comments": int(r.comments),
                    "posts": int(r.posts),
                    "sessions": int(r.sessions),
                }
                for r in ScrapingHealthRepository.own_comments_daily(days)
            ],
            "sessions": [
                {
                    "date": r.d.isoformat(),
                    "total": int(r.total),
                    "completed": int(r.completed),
                    "pending": int(r.pending),
                    "failed": int(r.failed),
                    # Finished cleanly and collected nothing -- the shape a
                    # dead session takes when nothing reports failure.
                    "empty_completed": int(r.empty_completed),
                    "comments_inserted": int(r.comments_inserted),
                }
                for r in ScrapingHealthRepository.sessions_daily(days)
            ],
        }

    @staticmethod
    def comment_coverage(days: int = COVERAGE_WINDOW_DAYS) -> dict:
        """Are we getting all the comments that exist?

        Two separate measures, because they answer different questions and
        conflating them produces a scary number that isn't true:

          reach       -- of the posts that HAVE comments and are inside the
                         scraper's own window, how many did we visit at all?
          completeness -- of the posts we did visit, how much of each post's
                         comment count did we actually capture?

        Posts older than the window are reported separately and never folded
        into the headline: the comments flow is not supposed to revisit them,
        so counting them as misses would invent a failure.
        """
        days = ScrapingHealthService._clamp(days)

        by_age = {}
        for r in ScrapingHealthRepository.comment_coverage_by_age(days):
            entry = by_age.setdefault(
                r.platform,
                {"platform": r.platform, "in_window": None, "older": None},
            )
            entry[r.bucket] = {
                "posts_with_comments": int(r.posts),
                "posts_touched": int(r.touched),
                "reach_pct": _pct(int(r.touched), int(r.posts)),
                "comments_available": int(r.comments_available),
                "comments_unseen": int(r.comments_unseen),
            }

        completeness = {
            r.platform: {
                "posts": int(r.posts),
                "ours": int(r.ours),
                "ours_top_level": int(r.ours_top_level),
                "brightdata": int(r.brightdata),
                # Over 100% is expected where we capture replies that Bright
                # Data's count excludes -- hence the top-level figure beside it.
                "coverage_pct": _pct(int(r.ours), int(r.brightdata)),
                "coverage_top_level_pct": _pct(int(r.ours_top_level), int(r.brightdata)),
                "posts_complete": int(r.posts_complete),
                "posts_comparable": int(r.posts_comparable),
                "complete_pct": _pct(int(r.posts_complete), int(r.posts_comparable)),
            }
            for r in ScrapingHealthRepository.comment_completeness(days)
        }

        platforms = []
        for platform in sorted(set(by_age) | set(completeness)):
            age = by_age.get(platform, {"in_window": None, "older": None})
            platforms.append(
                {
                    "platform": platform,
                    "in_window": age.get("in_window"),
                    "older": age.get("older"),
                    "completeness": completeness.get(platform),
                }
            )

        return {"window_days": days, "platforms": platforms}
