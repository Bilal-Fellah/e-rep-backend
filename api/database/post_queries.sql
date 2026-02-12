CREATE TABLE posts (
    id BIGSERIAL PRIMARY KEY,                -- internal DB ID
    page_id UUID NOT NULL REFERENCES pages(uuid),
    platform VARCHAR(20) NOT NULL,           -- e.g., instagram, linkedin, tiktok
    post_id VARCHAR(100) NOT NULL,           -- ID from the JSON, unique per platform/page
    created_at TIMESTAMP NOT NULL,           -- post creation time (from JSON)
    url TEXT,                                -- post URL if available
    likes BIGINT,                            -- common metric
    comments BIGINT,                         -- common metric
    shares BIGINT,                            -- common metric or NULL if not available
    views BIGINT,                             -- playcount or view count if available
    caption TEXT,                             -- Instagram caption or LinkedIn text
    content_type VARCHAR(50),                 -- e.g., photo, video, carousel (Instagram)
    image_url TEXT,                           -- if applicable
    video_url TEXT,                           -- if applicable
    is_pinned BOOLEAN,                        -- Instagram pinned post
    extra_data JSONB,                         -- store full original post JSON
    UNIQUE(page_id, platform, post_id)       -- ensures no duplicate post per page/platform
);

-- Optional indexes for performance:
CREATE INDEX idx_posts_page_platform ON posts(page_id, platform);
CREATE INDEX idx_posts_created_at ON posts(created_at);
CREATE INDEX idx_posts_extra_data ON posts USING GIN (extra_data);

-- insertion
--instagram
WITH new_posts AS (
    SELECT DISTINCT ON (ph.page_id, post->>'id')
        ph.page_id,
        'instagram' AS platform,
        post->>'id' AS post_id,
        (post->>'datetime')::timestamp AS created_at,
        post->>'url' AS url,
        (post->>'likes')::bigint AS likes,
        (post->>'comments')::bigint AS comments,
        NULL::bigint AS shares,
        NULL::bigint AS views,
        post->>'caption' AS caption,
        post->>'content_type' AS content_type,
        post->>'image_url' AS image_url,
        post->>'video_url' AS video_url,
        (post->>'is_pinned')::boolean AS is_pinned,
        post AS extra_data
    FROM pages_history ph,
         LATERAL jsonb_array_elements(ph.data->'posts') AS post
    WHERE jsonb_typeof(ph.data->'posts') = 'array'          -- must be array
      AND post->>'id' IS NOT NULL                           -- skip null post_id
    ORDER BY ph.page_id, post->>'id', (post->>'datetime')::timestamp DESC
)
INSERT INTO posts (
    page_id, platform, post_id, created_at, url,
    likes, comments, shares, views,
    caption, content_type, image_url, video_url, is_pinned, extra_data
)
SELECT *
FROM new_posts
ON CONFLICT (page_id, platform, post_id) DO UPDATE
SET
    likes = EXCLUDED.likes,
    comments = EXCLUDED.comments,
    shares = EXCLUDED.shares,
    views = EXCLUDED.views,
    url = EXCLUDED.url,
    caption = EXCLUDED.caption,
    content_type = EXCLUDED.content_type,
    image_url = EXCLUDED.image_url,
    video_url = EXCLUDED.video_url,
    is_pinned = EXCLUDED.is_pinned,
    extra_data = EXCLUDED.extra_data
RETURNING id, page_id, platform, post_id, likes, comments, shares, views, extra_data;

-- linkedin
WITH new_posts AS (
    SELECT DISTINCT ON (ph.page_id, post->>'post_id')
        ph.page_id,
        'linkedin' AS platform,
        post->>'post_id' AS post_id,
        (post->>'date')::timestamp AS created_at,
        post->>'post_url' AS url,
        (post->>'likes_count')::bigint AS likes,
        (post->>'comments_count')::bigint AS comments,
        NULL::bigint AS shares,
        NULL::bigint AS views,
        post->>'text' AS caption,
        'text' AS content_type,
        NULL AS image_url,
        NULL AS video_url,
        NULL::boolean AS is_pinned,
        post AS extra_data
    FROM pages_history ph,
         LATERAL jsonb_array_elements(ph.data->'updates') AS post
    WHERE jsonb_typeof(ph.data->'updates') = 'array'
      AND post->>'post_id' IS NOT NULL
    ORDER BY ph.page_id, post->>'post_id', (post->>'date')::timestamp DESC
)
INSERT INTO posts (
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
    extra_data
)
SELECT * FROM new_posts
ON CONFLICT (page_id, platform, post_id) DO UPDATE
SET
    likes = EXCLUDED.likes,
    comments = EXCLUDED.comments,
    caption = EXCLUDED.caption,
    url = EXCLUDED.url,
    extra_data = EXCLUDED.extra_data;

-- tiktok
WITH new_posts AS (
    SELECT DISTINCT ON (ph.page_id, post->>'video_id')
        ph.page_id,
        'tiktok' AS platform,
        post->>'video_id' AS post_id,
        (post->>'create_date')::timestamptz AS created_at,
        post->>'video_url' AS url,
        (post->>'favorites_count')::bigint AS likes,
        (post->>'commentcount')::bigint AS comments,
        (post->>'share_count')::bigint AS shares,
        (post->>'playcount')::bigint AS views,
        NULL AS caption,
        'video' AS content_type,
        post->>'cover_image' AS image_url,
        post->>'video_url' AS video_url,
        NULL::boolean AS is_pinned,
        post AS extra_data
    FROM pages_history ph,
         LATERAL jsonb_array_elements(ph.data->'top_videos') AS post
    WHERE jsonb_typeof(ph.data->'top_videos') = 'array'
      AND post->>'video_id' IS NOT NULL
    ORDER BY ph.page_id, post->>'video_id', (post->>'create_date')::timestamptz DESC
)
INSERT INTO posts (
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
    extra_data
)
SELECT * FROM new_posts
ON CONFLICT (page_id, platform, post_id) DO UPDATE
SET
    likes = EXCLUDED.likes,
    comments = EXCLUDED.comments,
    shares = EXCLUDED.shares,
    views = EXCLUDED.views,
    image_url = EXCLUDED.image_url,
    video_url = EXCLUDED.video_url,
    extra_data = EXCLUDED.extra_data;

-- youtube
WITH new_posts AS (
    SELECT DISTINCT ON (ph.page_id, post->>'video_id')
        ph.page_id,
        'youtube' AS platform,
        post->>'video_id' AS post_id,
        (post->>'published_at')::timestamp AS created_at,
        post->>'video_url' AS url,
        (post->>'like_count')::bigint AS likes,
        (post->>'comment_count')::bigint AS comments,
        NULL::bigint AS shares,
        (post->>'view_count')::bigint AS views,
        post->>'title' AS caption,
        'video' AS content_type,
        post->>'thumbnail_url' AS image_url,
        post->>'video_url' AS video_url,
        NULL::boolean AS is_pinned,
        post AS extra_data
    FROM pages_history ph,
         LATERAL jsonb_array_elements(ph.data->'videos') AS post
    WHERE jsonb_typeof(ph.data->'videos') = 'array'
      AND post->>'video_id' IS NOT NULL
)
INSERT INTO posts (
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
    extra_data
)
SELECT * FROM new_posts
ON CONFLICT (page_id, platform, post_id) DO UPDATE
SET
    likes = EXCLUDED.likes,
    comments = EXCLUDED.comments,
    views = EXCLUDED.views,
    caption = EXCLUDED.caption,
    extra_data = EXCLUDED.extra_data;

-- tracking post mertics
CREATE TABLE posts_history (
    id BIGSERIAL PRIMARY KEY,
    post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
    recorded_at TIMESTAMP NOT NULL DEFAULT now(), -- snapshot timestamp
    likes BIGINT,
    comments BIGINT,
    shares BIGINT,
    views BIGINT,
    extra_data JSONB
);

CREATE INDEX idx_posts_history_post_id ON posts_history(post_id);
CREATE INDEX idx_posts_history_recorded_at ON posts_history(recorded_at);


-- insertion into posts_history
WITH new_posts AS (
    SELECT DISTINCT ON (ph.page_id, post->>'id')
        ph.page_id,
        'instagram' AS platform,
        post->>'id' AS post_id,
        (post->>'datetime')::timestamp AS created_at,
        post->>'url' AS url,
        (post->>'likes')::bigint AS likes,
        (post->>'comments')::bigint AS comments,
        NULL::bigint AS shares,
        NULL::bigint AS views,
        post->>'caption' AS caption,
        post->>'content_type' AS content_type,
        post->>'image_url' AS image_url,
        post->>'video_url' AS video_url,
        (post->>'is_pinned')::boolean AS is_pinned,
        post AS extra_data
    FROM pages_history ph,
         LATERAL jsonb_array_elements(ph.data->'posts') AS post
    WHERE jsonb_typeof(ph.data->'posts') = 'array'
      AND post->>'id' IS NOT NULL
    ORDER BY ph.page_id, post->>'id', (post->>'datetime')::timestamp DESC
),
upserted AS (
    INSERT INTO posts (
        page_id, platform, post_id, created_at, url,
        likes, comments, shares, views,
        caption, content_type, image_url, video_url, is_pinned, extra_data
    )
    SELECT *
    FROM new_posts
    ON CONFLICT (page_id, platform, post_id) DO UPDATE
    SET
        likes = EXCLUDED.likes,
        comments = EXCLUDED.comments,
        shares = EXCLUDED.shares,
        views = EXCLUDED.views,
        url = EXCLUDED.url,
        caption = EXCLUDED.caption,
        content_type = EXCLUDED.content_type,
        image_url = EXCLUDED.image_url,
        video_url = EXCLUDED.video_url,
        is_pinned = EXCLUDED.is_pinned,
        extra_data = EXCLUDED.extra_data
    RETURNING id, likes, comments, shares, views, extra_data
)
INSERT INTO posts_history (post_id, recorded_at, likes, comments, shares, views, extra_data)
SELECT id, now(), likes, comments, shares, views, extra_data
FROM upserted;
