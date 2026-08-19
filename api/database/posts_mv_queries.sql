-- =============================================================================
-- posts_mv_queries.sql
--
-- Replaces the posts + posts_history tables with two materialized views.
--
-- Design rationale
-- ----------------
-- Both tables are fully derived from pages_history, so keeping standalone
-- tables requires manual INSERT scripts that must be re-run after every
-- scrape cycle. A materialized view removes that sync burden: a single
-- REFRESH MATERIALIZED VIEW CONCURRENTLY replaces all INSERT logic.
--
-- posts_history_mv  – one row per (page, platform, post_id, snapshot)
--                     equivalent to posts_history; full time-series.
-- posts_mv          – one row per (page, platform, post_id), latest snapshot
--                     equivalent to posts; current state of each post.
-- =============================================================================


-- =============================================================================
-- 1.  posts_history_mv
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS posts_mv CASCADE;
DROP MATERIALIZED VIEW IF EXISTS posts_history_mv CASCADE;

CREATE MATERIALIZED VIEW posts_history_mv AS
SELECT DISTINCT ON (page_id, platform, post_id, recorded_at)
    page_id,
    platform,
    recorded_at,
    post_id,
    created_at,
    url,
    likes,
    comments,
    shares,
    views,
    caption,
    content_type,
    image_url,
    video_url,
    is_pinned,
    extra_data
FROM (
    -- ── Instagram ──────────────────────────────────────────────────────────────
    SELECT
        ph.page_id,
        'instagram'::varchar(20)                                AS platform,
        ph.recorded_at,
        post->>'id'                                             AS post_id,
        COALESCE((post->>'datetime')::timestamp, ph.recorded_at) AS created_at,
        post->>'url'                                            AS url,
        COALESCE((post->>'likes')::bigint, (post->>'likes_count')::bigint, 0) AS likes,
        COALESCE((post->>'comments')::bigint, (post->>'comments_count')::bigint, 0) AS comments,
        NULL::bigint                                            AS shares,
        NULL::bigint                                            AS views,
        post->>'caption'                                        AS caption,
        post->>'content_type'                                   AS content_type,
        post->>'image_url'                                      AS image_url,
        post->>'video_url'                                      AS video_url,
        (post->>'is_pinned')::boolean                           AS is_pinned,
        post                                                    AS extra_data
    FROM pages_history ph
    JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'instagram'
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(ph.data->'posts', '[]'::jsonb)
    ) AS post
    WHERE jsonb_typeof(ph.data->'posts') = 'array'
      AND post->>'id' IS NOT NULL

    UNION ALL

    -- ── LinkedIn ──────────────────────────────────────────────────────────────
    SELECT
        ph.page_id,
        'linkedin'::varchar(20)                                 AS platform,
        ph.recorded_at,
        post->>'post_id'                                        AS post_id,
        COALESCE((post->>'date')::timestamp, ph.recorded_at)    AS created_at,
        post->>'post_url'                                       AS url,
        COALESCE((post->>'likes_count')::bigint, (post->>'likes')::bigint, 0) AS likes,
        COALESCE((post->>'comments_count')::bigint, (post->>'comments')::bigint, 0) AS comments,
        NULL::bigint                                            AS shares,  -- repost is a nested object, no simple count
        NULL::bigint                                            AS views,
        post->>'text'                                           AS caption,
        'text'::varchar(50)                                     AS content_type,
        NULL::text                                              AS image_url,
        NULL::text                                              AS video_url,
        NULL::boolean                                           AS is_pinned,
        post                                                    AS extra_data
    FROM pages_history ph
    JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'linkedin'
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(ph.data->'updates', '[]'::jsonb)
    ) AS post
    WHERE jsonb_typeof(ph.data->'updates') = 'array'
      AND post->>'post_id' IS NOT NULL

    UNION ALL

    -- ── TikTok ────────────────────────────────────────────────────────────────
    SELECT
        ph.page_id,
        'tiktok'::varchar(20)                                  AS platform,
        ph.recorded_at,
        post->>'video_id'                                      AS post_id,
        COALESCE((post->>'create_date')::timestamp, ph.recorded_at) AS created_at,
        post->>'video_url'                                     AS url,
        COALESCE((post->>'favorites_count')::bigint, (post->>'diggcount')::bigint, (post->>'likes')::bigint, 0) AS likes,
        COALESCE((post->>'commentcount')::bigint, (post->>'comments_count')::bigint, (post->>'comments')::bigint, 0) AS comments,
        COALESCE((post->>'share_count')::bigint, (post->>'shares')::bigint, 0) AS shares,
        COALESCE((post->>'playcount')::bigint, (post->>'views')::bigint, 0) AS views,
        NULL::text                                             AS caption,
        'video'::varchar(50)                                   AS content_type,
        post->>'cover_image'                                   AS image_url,
        post->>'video_url'                                     AS video_url,
        NULL::boolean                                          AS is_pinned,
        post                                                   AS extra_data
    FROM pages_history ph
    JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'tiktok'
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(ph.data->'top_videos', '[]'::jsonb)
    ) AS post
    WHERE jsonb_typeof(ph.data->'top_videos') = 'array'
      AND post->>'video_id' IS NOT NULL

    UNION ALL

    -- ── YouTube ───────────────────────────────────────────────────────────────
    SELECT
        ph.page_id,
        'youtube'::varchar(20)                                 AS platform,
        ph.recorded_at,
        post->>'video_id'                                      AS post_id,
        COALESCE((post->>'published_at')::timestamp, ph.recorded_at) AS created_at,
        post->>'video_url'                                     AS url,
        COALESCE((post->>'like_count')::bigint, (post->>'likes')::bigint, 0) AS likes,
        COALESCE((post->>'comment_count')::bigint, (post->>'comments_count')::bigint, (post->>'comments')::bigint, 0) AS comments,
        NULL::bigint                                           AS shares,
        COALESCE((post->>'view_count')::bigint, (post->>'views')::bigint, 0) AS views,
        post->>'title'                                         AS caption,
        'video'::varchar(50)                                   AS content_type,
        post->>'thumbnail_url'                                 AS image_url,
        post->>'video_url'                                     AS video_url,
        NULL::boolean                                          AS is_pinned,
        post                                                   AS extra_data
    FROM pages_history ph
    JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'youtube'
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(ph.data->'top_videos', '[]'::jsonb)
    ) AS post
    WHERE jsonb_typeof(ph.data->'top_videos') = 'array'
      AND post->>'video_id' IS NOT NULL

    UNION ALL

    -- ── X / Twitter ───────────────────────────────────────────────────────────
    SELECT
        ph.page_id,
        'x'::varchar(20)                                       AS platform,
        ph.recorded_at,
        COALESCE(post->>'post_id', post->>'id')                AS post_id,
        COALESCE((post->>'date_posted')::timestamp, (post->>'created_at')::timestamp, ph.recorded_at) AS created_at,
        post->>'url'                                           AS url,
        COALESCE((post->>'likes')::bigint, (post->>'like_count')::bigint, 0) AS likes,
        COALESCE((post->>'replies')::bigint, (post->>'comments')::bigint, 0) AS comments,
        COALESCE((post->>'reposts')::bigint, (post->>'shares')::bigint, 0) AS shares,
        COALESCE((post->>'views')::bigint, 0)                  AS views,
        post->>'content'                                       AS caption,
        'post'::varchar(50)                                    AS content_type,
        NULL::text                                             AS image_url,
        NULL::text                                             AS video_url,
        NULL::boolean                                          AS is_pinned,
        post                                                   AS extra_data
    FROM pages_history ph
    JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'x'
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(ph.data->'posts', '[]'::jsonb)
    ) AS post
    WHERE jsonb_typeof(ph.data->'posts') = 'array'
      AND COALESCE(post->>'post_id', post->>'id') IS NOT NULL

    UNION ALL

    -- ── Facebook ──────────────────────────────────────────────────────────────
    -- Each pages_history row is one Facebook post (flat, not an array).
    SELECT
        ph.page_id,
        'facebook'::varchar(20)                                AS platform,
        ph.recorded_at,
        COALESCE(ph.data->>'post_id', ph.data->>'postId')       AS post_id,
        CASE
            WHEN ph.data->>'date_posted' IS NOT NULL AND ph.data->>'date_posted' != '' THEN (ph.data->>'date_posted')::timestamp
            WHEN ph.data->>'time' IS NOT NULL AND ph.data->>'time' != '' THEN (ph.data->>'time')::timestamp
            WHEN ph.data->>'timestamp' ~ '^[0-9]+$' THEN (to_timestamp((ph.data->>'timestamp')::bigint) AT TIME ZONE 'UTC')::timestamp
            ELSE ph.recorded_at
        END                                                    AS created_at,
        ph.data->>'url'                                        AS url,
        COALESCE(
            (ph.data->>'likes')::bigint,
            (ph.data->>'topReactionsCount')::bigint,
            (ph.data->>'reactionLikeCount')::bigint,
            0
        )                                                      AS likes,
        COALESCE(
            (ph.data->>'num_comments')::bigint,
            (ph.data->>'comments')::bigint,
            0
        )                                                      AS comments,
        COALESCE(
            (ph.data->>'num_shares')::bigint,
            (ph.data->>'shares')::bigint,
            0
        )                                                      AS shares,
        COALESCE(
            (ph.data->>'video_view_count')::bigint,
            (ph.data->>'play_count')::bigint,
            (ph.data->>'videoPostViewCount')::bigint,
            (ph.data->>'viewsCount')::bigint,
            0
        )                                                      AS views,
        COALESCE(ph.data->>'content', ph.data->>'text')        AS caption,
        ph.data->>'post_type'                                  AS content_type,
        ph.data->>'post_image'                                 AS image_url,
        NULL::text                                             AS video_url,
        NULL::boolean                                          AS is_pinned,
        ph.data                                                AS extra_data
    FROM pages_history ph
    JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'facebook'
    WHERE COALESCE(ph.data->>'post_id', ph.data->>'postId') IS NOT NULL
) raw_posts
ORDER BY page_id, platform, post_id, recorded_at DESC;


-- ── Indexes on posts_history_mv ───────────────────────────────────────────
-- CONCURRENTLY refresh requires a unique index.
CREATE UNIQUE INDEX idx_phm_unique
    ON posts_history_mv (page_id, platform, post_id, recorded_at);

CREATE INDEX idx_phm_page_platform
    ON posts_history_mv (page_id, platform);

CREATE INDEX idx_phm_recorded_at
    ON posts_history_mv (recorded_at DESC);

CREATE INDEX idx_phm_created_at
    ON posts_history_mv (created_at DESC);


-- =============================================================================
-- 2.  posts_mv  (latest snapshot per post)
-- =============================================================================
CREATE MATERIALIZED VIEW posts_mv AS
SELECT DISTINCT ON (page_id, platform, post_id)
    page_id,
    platform,
    post_id,
    created_at,
    url,
    likes,
    comments,
    shares,
    views,
    caption,
    content_type,
    image_url,
    video_url,
    is_pinned,
    extra_data,
    recorded_at   -- timestamp of the snapshot this data comes from
FROM posts_history_mv
ORDER BY page_id, platform, post_id, recorded_at DESC;


-- ── Indexes on posts_mv ───────────────────────────────────────────────────
-- CONCURRENTLY refresh requires a unique index.
CREATE UNIQUE INDEX idx_pm_unique
    ON posts_mv (page_id, platform, post_id);

CREATE INDEX idx_pm_page_platform
    ON posts_mv (page_id, platform);

CREATE INDEX idx_pm_created_at
    ON posts_mv (created_at DESC);


-- =============================================================================
-- 3.  Refresh
-- =============================================================================
-- Run this after every scrape cycle (or on a schedule).
-- posts_history_mv must be refreshed first because posts_mv depends on it.

REFRESH MATERIALIZED VIEW CONCURRENTLY posts_history_mv;
REFRESH MATERIALIZED VIEW CONCURRENTLY posts_mv;
