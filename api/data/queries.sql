-- Enable timing
\timing

-- Run your first query
EXPLAIN ANALYZE
SELECT
    id,
    page_id,
    recorded_at,
    jsonb_array_elements(data->'posts')->>'likes' AS likes
FROM pages_history ph join pages p on p.uuid = ph.page_id where p.platform = 'instagram';
-- Run your second query

EXPLAIN ANALYZE
SELECT
    id,
    page_id,
    recorded_at,
    jsonb_array_elements(data->'posts')
FROM pages_history ph join pages p on p.uuid = ph.page_id where p.platform = 'instagram';

-- Disable timing (optional)
\timing off




-- create mv
CREATE MATERIALIZED VIEW page_posts_metrics_mv AS
SELECT 
    ph.id AS history_id,
    ph.page_id AS page_id,
    p.platform AS platform,
    ph.recorded_at AS recorded_at,
    e.id AS entity_id,
    e.name AS entity_name,
    p.name AS page_name,
    CASE 
        WHEN p.platform = 'instagram'
            AND jsonb_typeof(COALESCE(ph.data->'posts', '[]'::jsonb)) = 'array'
        THEN 
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id',               post->>'id',
                        'datetime',         post->>'datetime',
                        'comments',         post->'comments',
                        'likes',            post->'likes'
                    )
                )
                FROM jsonb_array_elements(COALESCE(ph.data->'posts', '[]'::jsonb)) AS post
            )

        WHEN p.platform = 'linkedin'
            AND jsonb_typeof(COALESCE(ph.data->'updates', '[]'::jsonb)) = 'array'
        THEN 
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'post_id',          post->>'post_id',
                        'date',             post->>'date',
                        'comments_count',   post->'comments_count',
                        'likes_count',      post->'likes_count'
                    )
                )
                FROM jsonb_array_elements(COALESCE(ph.data->'updates', '[]'::jsonb)) AS post
            )

        WHEN p.platform = 'tiktok'
            AND jsonb_typeof(COALESCE(ph.data->'top_videos', '[]'::jsonb)) = 'array'
        THEN 
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'video_id',         post->>'video_id',
                        'create_date',      post->>'create_date',
                        'commentcount',     post->'commentcount',
                        'share_count',      post->'share_count',
                        'favorites_count',  post->'favorites_count',
                        'playcount',        post->'playcount'
                    )
                )
                FROM jsonb_array_elements(COALESCE(ph.data->'top_videos', '[]'::jsonb)) AS post
            )

        ELSE '[]'::jsonb
    END AS posts_metrics
FROM pages_history ph
JOIN pages p ON p.uuid = ph.page_id
JOIN entities e ON e.id = p.entity_id;

-- check the list of materialized views
SELECT matviewname FROM pg_matviews WHERE matviewname = 'page_posts_metrics_mv';


-- to be done someday:
CREATE INDEX idx_ppmm_page_id ON page_posts_metrics_mv (page_id);
CREATE INDEX idx_ppmm_platform ON page_posts_metrics_mv (platform);
CREATE INDEX idx_ppmm_recorded_at ON page_posts_metrics_mv (recorded_at);
-- and 
CREATE INDEX idx_ppmm_page_time 
ON page_posts_metrics_mv (page_id, recorded_at DESC);


-- refresh mv
CREATE UNIQUE INDEX idx_ppmm_unique
ON page_posts_metrics_mv (history_id);
--\
REFRESH MATERIALIZED VIEW CONCURRENTLY page_posts_metrics_mv;
