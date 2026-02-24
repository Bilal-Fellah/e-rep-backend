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
CREATE MATERIALIZED VIEW posts_history_mv AS

-- ── Instagram ──────────────────────────────────────────────────────────────
SELECT
    ph.page_id,
    'instagram'::varchar(20)        AS platform,
    ph.recorded_at,
    post->>'id'                     AS post_id,
    (post->>'datetime')::timestamp  AS created_at,
    post->>'url'                    AS url,
    (post->>'likes')::bigint        AS likes,
    (post->>'comments')::bigint     AS comments,
    NULL::bigint                    AS shares,
    NULL::bigint                    AS views,
    post->>'caption'                AS caption,
    post->>'content_type'           AS content_type,
    post->>'image_url'              AS image_url,
    post->>'video_url'              AS video_url,
    (post->>'is_pinned')::boolean   AS is_pinned,
    post                            AS extra_data
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
    'linkedin'::varchar(20)              AS platform,
    ph.recorded_at,
    post->>'post_id'                     AS post_id,
    (post->>'date')::timestamp           AS created_at,
    post->>'post_url'                    AS url,
    (post->>'likes_count')::bigint       AS likes,
    (post->>'comments_count')::bigint    AS comments,
    NULL::bigint                         AS shares,  -- repost is a nested object, no simple count
    NULL::bigint                         AS views,
    post->>'text'                        AS caption,
    'text'::varchar(50)                  AS content_type,
    NULL::text                           AS image_url,
    NULL::text                           AS video_url,
    NULL::boolean                        AS is_pinned,
    post                                 AS extra_data
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
    'tiktok'::varchar(20)                   AS platform,
    ph.recorded_at,
    post->>'video_id'                       AS post_id,
    (post->>'create_date')::timestamptz     AS created_at,
    post->>'video_url'                      AS url,
    (post->>'favorites_count')::bigint      AS likes,
    (post->>'commentcount')::bigint         AS comments,
    (post->>'share_count')::bigint          AS shares,
    (post->>'playcount')::bigint            AS views,
    NULL::text                              AS caption,
    'video'::varchar(50)                    AS content_type,
    post->>'cover_image'                    AS image_url,
    post->>'video_url'                      AS video_url,
    NULL::boolean                           AS is_pinned,
    post                                    AS extra_data
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
    'youtube'::varchar(20)                  AS platform,
    ph.recorded_at,
    post->>'video_id'                       AS post_id,
    (post->>'published_at')::timestamp      AS created_at,
    post->>'video_url'                      AS url,
    (post->>'like_count')::bigint           AS likes,
    (post->>'comment_count')::bigint        AS comments,
    NULL::bigint                            AS shares,
    (post->>'view_count')::bigint           AS views,
    post->>'title'                          AS caption,
    'video'::varchar(50)                    AS content_type,
    post->>'thumbnail_url'                  AS image_url,
    post->>'video_url'                      AS video_url,
    NULL::boolean                           AS is_pinned,
    post                                    AS extra_data
FROM pages_history ph
JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'youtube'
CROSS JOIN LATERAL jsonb_array_elements(
    COALESCE(ph.data->'videos', '[]'::jsonb)
) AS post
WHERE jsonb_typeof(ph.data->'videos') = 'array'
  AND post->>'video_id' IS NOT NULL

UNION ALL

-- ── X / Twitter ───────────────────────────────────────────────────────────
SELECT
    ph.page_id,
    'x'::varchar(20)                        AS platform,
    ph.recorded_at,
    post->>'post_id'                        AS post_id,
    (post->>'date_posted')::timestamp       AS created_at,
    post->>'url'                            AS url,
    (post->>'likes')::bigint                AS likes,
    (post->>'replies')::bigint              AS comments,
    (post->>'reposts')::bigint              AS shares,
    (post->>'views')::bigint                AS views,
    post->>'content'                        AS caption,
    'post'::varchar(50)                     AS content_type,
    NULL::text                              AS image_url,
    NULL::text                              AS video_url,
    NULL::boolean                           AS is_pinned,
    post                                    AS extra_data
FROM pages_history ph
JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'x'
CROSS JOIN LATERAL jsonb_array_elements(
    COALESCE(ph.data->'posts', '[]'::jsonb)
) AS post
WHERE jsonb_typeof(ph.data->'posts') = 'array'
  AND post->>'post_id' IS NOT NULL

UNION ALL

-- ── Facebook ──────────────────────────────────────────────────────────────
-- Each pages_history row is one Facebook post (flat, not an array).
SELECT
    ph.page_id,
    'facebook'::varchar(20)                 AS platform,
    ph.recorded_at,
    ph.data->>'post_id'                     AS post_id,
    (ph.data->>'date_posted')::timestamp    AS created_at,
    ph.data->>'url'                         AS url,
    (ph.data->>'likes')::bigint             AS likes,
    (ph.data->>'num_comments')::bigint      AS comments,
    (ph.data->>'num_shares')::bigint        AS shares,
    COALESCE(
        (ph.data->>'video_view_count')::bigint,
        (ph.data->>'play_count')::bigint
    )                                       AS views,
    ph.data->>'content'                     AS caption,
    ph.data->>'post_type'                   AS content_type,
    ph.data->>'post_image'                  AS image_url,
    NULL::text                              AS video_url,
    NULL::boolean                           AS is_pinned,
    ph.data                                 AS extra_data
FROM pages_history ph
JOIN pages p ON p.uuid = ph.page_id AND p.platform = 'facebook'
WHERE ph.data->>'post_id' IS NOT NULL;


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


-- =============================================================================
-- 4.  Example queries (for reference)
-- =============================================================================

-- Latest metrics for all posts of a given page:
-- SELECT * FROM posts_mv WHERE page_id = '<uuid>' ORDER BY created_at DESC;

-- Full metric history for a specific post:
-- SELECT recorded_at, likes, comments, shares, views
-- FROM posts_history_mv
-- WHERE page_id = '<uuid>' AND platform = 'instagram' AND post_id = '<id>'
-- ORDER BY recorded_at;

-- Gained metrics between two consecutive snapshots:
-- SELECT
--     curr.post_id,
--     curr.recorded_at,
--     curr.likes  - prev.likes  AS gained_likes,
--     curr.comments - prev.comments AS gained_comments
-- FROM posts_history_mv curr
-- JOIN posts_history_mv prev
--   ON  prev.page_id  = curr.page_id
--  AND  prev.platform = curr.platform
--  AND  prev.post_id  = curr.post_id
--  AND  prev.recorded_at = (
--         SELECT MAX(h2.recorded_at)
--         FROM posts_history_mv h2
--         WHERE h2.page_id  = curr.page_id
--           AND h2.platform = curr.platform
--           AND h2.post_id  = curr.post_id
--           AND h2.recorded_at < curr.recorded_at
--      )
-- WHERE curr.page_id = '<uuid>';
