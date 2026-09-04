# Data-access for the admin "Scraping Health" report.
#
# Every query here was validated against the production database before
# being wired up. They are raw SQL rather than ORM constructs because they
# are aggregate- and JSONB-heavy, and because the JSONB field checks need
# nested CASE expressions: CASE is one of the few Postgres constructs with
# guaranteed evaluation order, so jsonb_array_length() can't be run against
# a scalar by a predicate that was reordered.
from sqlalchemy import text

from api import db
from api.utils.logging_utils import instrument_repository_class

# Per-platform key names, established by auditing the real payloads rather
# than by assuming a convention -- the scrapers disagree with each other.
POSTS_KEY = (
    "CASE p.platform WHEN 'tiktok' THEN 'top_videos' WHEN 'youtube' THEN 'top_videos' "
    "WHEN 'linkedin' THEN 'updates' ELSE 'posts' END"
)
FOLLOWERS_KEY = (
    "CASE p.platform WHEN 'youtube' THEN 'subscribers' "
    "WHEN 'facebook' THEN 'page_followers' ELSE 'followers' END"
)
# Every spelling posts_mv_queries.sql accepts. Deliberately wider than
# PageHistoryRepository.validate_data_structure's list, which misses the
# snake_case variants the scrapers actually emit.
LIKE_KEYS = "ARRAY['likes','likes_count','likesCount','like_count','diggcount','favorites_count']"
COMMENT_KEYS = (
    "ARRAY['comments','comments_count','commentsCount','comment_count',"
    "'commentcount','num_comments','replies']"
)


@instrument_repository_class
class ScrapingHealthRepository:
    """Read-only aggregates behind the Scraping Health page."""

    @staticmethod
    def brightdata_daily(days: int) -> list:
        """Per day and platform: what Bright Data actually delivered."""
        return db.session.execute(
            text(f"""
            WITH base AS (
                SELECT h.recorded_at::date AS d, p.platform, h.data,
                       {POSTS_KEY} AS pk, {FOLLOWERS_KEY} AS fk
                FROM pages_history h
                JOIN pages p ON p.uuid = h.page_id
                JOIN entities e ON e.id = p.entity_id
                WHERE e.to_scrape IS TRUE AND h.source = 'brightdata'
                  AND h.recorded_at >= current_date - CAST(:days AS integer)
            ),
            flags AS (
                SELECT d, platform,
                    (data ? 'error' AND data->>'error' IS NOT NULL) AS has_error,
                    (data ->> fk) IS NOT NULL AS has_followers,
                    CASE WHEN platform = 'facebook' THEN (data ? 'post_id')
                         WHEN jsonb_typeof(data -> pk) = 'array'
                           THEN CASE WHEN jsonb_array_length(data -> pk) > 0
                                     THEN true ELSE false END
                         ELSE false END AS has_posts,
                    CASE WHEN platform = 'facebook' THEN (data ?| {LIKE_KEYS})
                         WHEN jsonb_typeof(data -> pk) = 'array'
                           THEN CASE WHEN jsonb_array_length(data -> pk) > 0
                                     THEN (data -> pk -> 0) ?| {LIKE_KEYS} ELSE false END
                         ELSE false END AS has_likes,
                    CASE WHEN platform = 'facebook' THEN (data ?| {COMMENT_KEYS})
                         WHEN jsonb_typeof(data -> pk) = 'array'
                           THEN CASE WHEN jsonb_array_length(data -> pk) > 0
                                     THEN (data -> pk -> 0) ?| {COMMENT_KEYS} ELSE false END
                         ELSE false END AS has_comments
                FROM base
            )
            SELECT d, platform, count(*) AS rows,
                   count(*) FILTER (WHERE has_error)         AS errors,
                   count(*) FILTER (WHERE NOT has_followers) AS no_followers,
                   count(*) FILTER (WHERE NOT has_posts)     AS no_posts,
                   count(*) FILTER (WHERE NOT has_likes)     AS no_likes,
                   count(*) FILTER (WHERE NOT has_comments)  AS no_comments
            FROM flags GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC
            """),
            {"days": days},
        ).all()

    @staticmethod
    def brightdata_errors(days: int) -> list:
        """The error strings Bright Data returned, most common first."""
        return db.session.execute(
            text("""
            SELECT left(h.data->>'error', 80) AS error, count(*) AS n
            FROM pages_history h JOIN pages p ON p.uuid = h.page_id
            WHERE h.source = 'brightdata'
              AND h.recorded_at >= current_date - CAST(:days AS integer)
              AND h.data->>'error' IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 12
            """),
            {"days": days},
        ).all()

    @staticmethod
    def own_profile_daily(days: int) -> list:
        """Own-scraper profile passes: attempted vs actually inserted."""
        return db.session.execute(
            text("""
            SELECT scraped_at::date AS d, platform,
                   count(*) AS attempted,
                   count(*) FILTER (WHERE profile_inserted) AS inserted
            FROM scraping_profile_results
            WHERE scraped_at >= current_date - CAST(:days AS integer)
            GROUP BY 1, 2 ORDER BY 1 DESC, 2
            """),
            {"days": days},
        ).all()

    @staticmethod
    def own_comments_daily(days: int) -> list:
        """Own-scraper comment collection, by day and platform."""
        return db.session.execute(
            text("""
            SELECT recorded_at::date AS d, platform,
                   count(*) AS comments,
                   count(DISTINCT post_id) AS posts,
                   count(DISTINCT scraping_session_id) AS sessions
            FROM comments
            WHERE recorded_at >= current_date - CAST(:days AS integer)
            GROUP BY 1, 2 ORDER BY 1 DESC, 2
            """),
            {"days": days},
        ).all()

    @staticmethod
    def sessions_daily(days: int) -> list:
        """Session outcomes per day. `empty_completed` is the silent-failure
        shape: finished cleanly, collected nothing."""
        return db.session.execute(
            text("""
            SELECT created_at::date AS d,
                   count(*) AS total,
                   count(*) FILTER (WHERE status = 'completed') AS completed,
                   count(*) FILTER (WHERE status = 'pending')   AS pending,
                   count(*) FILTER (WHERE status = 'failed')    AS failed,
                   count(*) FILTER (WHERE status = 'completed' AND comments_inserted = 0)
                       AS empty_completed,
                   COALESCE(sum(comments_inserted), 0) AS comments_inserted
            FROM scraping_sessions
            WHERE created_at >= current_date - CAST(:days AS integer)
            GROUP BY 1 ORDER BY 1 DESC
            """),
            {"days": days},
        ).all()

    @staticmethod
    def comment_coverage_by_age(days: int) -> list:
        """Posts that have comments, split by post age, and how many we have
        collected from. The age split is what makes this fair: the comments
        flow only targets recent posts (scraping_start_date_days), so old
        posts are out of scope by design, not by failure."""
        return db.session.execute(
            text("""
            SELECT m.platform,
                   CASE WHEN m.created_at >= now() - CAST(:days AS integer) * interval '1 day'
                             THEN 'in_window' ELSE 'older' END AS bucket,
                   count(*) AS posts,
                   count(*) FILTER (WHERE c.post_id IS NOT NULL) AS touched,
                   COALESCE(sum(m.comments), 0) AS comments_available,
                   COALESCE(sum(m.comments) FILTER (WHERE c.post_id IS NULL), 0) AS comments_unseen
            FROM posts_mv m
            LEFT JOIN (SELECT DISTINCT platform, page_id, post_id FROM comments) c
              ON c.post_id = m.post_id AND c.platform = m.platform
             AND c.page_id = m.page_id::text
            WHERE m.comments > 0
            GROUP BY 1, 2 ORDER BY 1, 2
            """),
            {"days": days},
        ).all()

    @staticmethod
    def comment_completeness(days: int) -> list:
        """For posts we did collect from: how our comment count compares to
        Bright Data's own count for the same post.

        Each post is compared against the BD snapshot CLOSEST IN TIME to
        when we scraped it. Comparing against the latest snapshot instead
        would charge us for every comment posted since.
        """
        return db.session.execute(
            text("""
            WITH scoped AS (
                -- Posts we visited recently. The window picks which posts are
                -- in scope; it must NOT filter the comment rows themselves,
                -- or a post collected over several days is compared to its
                -- full Bright Data count using only its last day's rows.
                SELECT platform, page_id, post_id
                FROM comments GROUP BY 1, 2, 3
                HAVING max(recorded_at) >= current_date - CAST(:days AS integer)
            ),
            ours AS (
                SELECT c.platform, c.page_id, c.post_id,
                       count(DISTINCT c.comment_id) AS scraped_all,
                       count(DISTINCT c.comment_id) FILTER (WHERE c.parent_comment_id IS NULL)
                           AS scraped_top,
                       max(c.recorded_at) AS scraped_at
                FROM comments c
                JOIN scoped s ON s.platform = c.platform AND s.page_id = c.page_id
                             AND s.post_id = c.post_id
                GROUP BY 1, 2, 3
            ),
            matched AS (
                SELECT DISTINCT ON (o.platform, o.page_id, o.post_id)
                       o.platform, o.scraped_all, o.scraped_top,
                       COALESCE(h.comments, 0) AS bd_comments
                FROM ours o
                JOIN posts_history_mv h
                  ON h.post_id = o.post_id AND h.platform = o.platform
                 AND h.page_id::text = o.page_id
                ORDER BY o.platform, o.page_id, o.post_id,
                         abs(extract(epoch FROM (h.recorded_at - o.scraped_at)))
            )
            SELECT platform,
                   count(*) AS posts,
                   COALESCE(sum(scraped_all), 0) AS ours,
                   COALESCE(sum(scraped_top), 0) AS ours_top_level,
                   COALESCE(sum(bd_comments), 0) AS brightdata,
                   count(*) FILTER (WHERE bd_comments > 0
                                    AND scraped_all::float / bd_comments >= 0.99) AS posts_complete,
                   count(*) FILTER (WHERE bd_comments > 0) AS posts_comparable
            FROM matched GROUP BY 1 ORDER BY 3 DESC
            """),
            {"days": days},
        ).all()
