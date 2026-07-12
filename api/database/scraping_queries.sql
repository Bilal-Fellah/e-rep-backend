-- Useful SQL queries for the scraping feature

-- ============================================================================
-- SCRAPING SESSIONS
-- ============================================================================

-- View all scraping sessions
SELECT 
    session_id,
    created_at,
    completed_at,
    posts_fetched,
    comments_inserted,
    status,
    error_message
FROM scraping_sessions
ORDER BY created_at DESC
LIMIT 20;

-- View active (pending) sessions
SELECT * FROM scraping_sessions
WHERE status = 'pending'
ORDER BY created_at DESC;

-- View failed sessions
SELECT * FROM scraping_sessions
WHERE status = 'failed'
ORDER BY created_at DESC;

-- Session statistics
SELECT 
    status,
    COUNT(*) as session_count,
    SUM(posts_fetched) as total_posts,
    SUM(comments_inserted) as total_comments,
    AVG(comments_inserted) as avg_comments_per_session
FROM scraping_sessions
GROUP BY status;

-- Sessions by date
SELECT 
    DATE(created_at) as date,
    COUNT(*) as sessions,
    SUM(posts_fetched) as posts,
    SUM(comments_inserted) as comments
FROM scraping_sessions
GROUP BY DATE(created_at)
ORDER BY date DESC;


-- ============================================================================
-- COMMENTS
-- ============================================================================

-- View recent comments
SELECT 
    id,
    page_id,
    platform,
    post_id,
    comment_id,
    text,
    author_username,
    likes_count,
    comment_timestamp,
    recorded_at
FROM comments
ORDER BY recorded_at DESC
LIMIT 20;

-- Comments by platform
SELECT 
    platform,
    COUNT(*) as comment_count,
    SUM(likes_count) as total_likes,
    AVG(likes_count) as avg_likes
FROM comments
GROUP BY platform
ORDER BY comment_count DESC;

-- Comments by session
SELECT 
    scraping_session_id,
    COUNT(*) as comment_count,
    MIN(recorded_at) as first_comment,
    MAX(recorded_at) as last_comment
FROM comments
WHERE scraping_session_id IS NOT NULL
GROUP BY scraping_session_id
ORDER BY first_comment DESC;

-- Top commented posts
SELECT 
    page_id,
    platform,
    post_id,
    COUNT(*) as comment_count,
    SUM(likes_count) as total_likes
FROM comments
GROUP BY page_id, platform, post_id
ORDER BY comment_count DESC
LIMIT 20;

-- Find comments with replies
SELECT 
    c1.comment_id as parent_comment,
    c1.text as parent_text,
    COUNT(c2.comment_id) as reply_count
FROM comments c1
LEFT JOIN comments c2 ON c1.comment_id = c2.parent_comment_id
    AND c1.page_id = c2.page_id
    AND c1.platform = c2.platform
    AND c1.post_id = c2.post_id
WHERE c2.comment_id IS NOT NULL
GROUP BY c1.comment_id, c1.text
ORDER BY reply_count DESC
LIMIT 20;


-- ============================================================================
-- COMBINED QUERIES
-- ============================================================================

-- Session completion details
SELECT 
    s.session_id,
    s.created_at,
    s.completed_at,
    s.posts_fetched,
    s.comments_inserted,
    COUNT(c.id) as actual_comment_count,
    s.status,
    ROUND(
        EXTRACT(EPOCH FROM (s.completed_at - s.created_at)) / 60, 
        2
    ) as duration_minutes
FROM scraping_sessions s
LEFT JOIN comments c ON s.session_id = c.scraping_session_id
WHERE s.completed_at IS NOT NULL
GROUP BY s.session_id, s.created_at, s.completed_at, s.posts_fetched, 
         s.comments_inserted, s.status
ORDER BY s.created_at DESC
LIMIT 20;

-- Posts without comments yet
SELECT 
    pm.page_id,
    pm.platform,
    pm.post_id,
    pm.url,
    pm.created_at,
    pm.recorded_at
FROM posts_mv pm
LEFT JOIN comments c ON pm.page_id = c.page_id 
    AND pm.platform = c.platform 
    AND pm.post_id = c.post_id
WHERE c.id IS NULL
    AND pm.recorded_at >= CURRENT_DATE - INTERVAL '1 day'
    AND pm.recorded_at < CURRENT_DATE
ORDER BY pm.recorded_at DESC
LIMIT 20;


-- ============================================================================
-- DATA QUALITY CHECKS
-- ============================================================================

-- Find duplicate comments (should be 0 due to unique constraint)
SELECT 
    page_id,
    platform,
    post_id,
    comment_id,
    COUNT(*) as duplicate_count
FROM comments
GROUP BY page_id, platform, post_id, comment_id
HAVING COUNT(*) > 1;

-- Comments without valid scraping session
SELECT COUNT(*) as orphaned_comments
FROM comments
WHERE scraping_session_id IS NOT NULL
    AND scraping_session_id NOT IN (SELECT session_id FROM scraping_sessions);

-- Sessions with comment count mismatch
SELECT 
    s.session_id,
    s.comments_inserted as recorded_count,
    COUNT(c.id) as actual_count,
    s.comments_inserted - COUNT(c.id) as difference
FROM scraping_sessions s
LEFT JOIN comments c ON s.session_id = c.scraping_session_id
GROUP BY s.session_id, s.comments_inserted
HAVING s.comments_inserted != COUNT(c.id);


-- ============================================================================
-- CLEANUP QUERIES (USE WITH CAUTION!)
-- ============================================================================

-- Delete comments older than 90 days (adjust as needed)
-- DELETE FROM comments 
-- WHERE recorded_at < CURRENT_DATE - INTERVAL '90 days';

-- Delete failed sessions older than 30 days
-- DELETE FROM scraping_sessions 
-- WHERE status = 'failed' 
--     AND created_at < CURRENT_DATE - INTERVAL '30 days';

-- Reset a stuck pending session to failed
-- UPDATE scraping_sessions 
-- SET status = 'failed', 
--     error_message = 'Session timeout - manually reset'
-- WHERE session_id = 'YOUR_SESSION_ID';
