-- =============================================================================
-- Missing Indexes for Performance Optimization
-- =============================================================================
-- These indexes are critical for ranking queries performance.
-- Run this script to add missing indexes on materialized views.
-- =============================================================================

-- Indexes for page_posts_metrics_mv (used by entity rankings and posts)
-- These were commented as "to be done someday" but are causing slow queries

-- Index on page_id for page-specific lookups
CREATE INDEX IF NOT EXISTS idx_ppmm_page_id 
    ON page_posts_metrics_mv (page_id);

-- Index on platform for platform-specific filters
CREATE INDEX IF NOT EXISTS idx_ppmm_platform 
    ON page_posts_metrics_mv (platform);

-- Index on recorded_at for date range filters (DESC for latest-first queries)
CREATE INDEX IF NOT EXISTS idx_ppmm_recorded_at 
    ON page_posts_metrics_mv (recorded_at DESC);

-- Composite index for page + time queries (get latest snapshot per page)
CREATE INDEX IF NOT EXISTS idx_ppmm_page_time 
    ON page_posts_metrics_mv (page_id, recorded_at DESC);

-- CRITICAL: Index on entity_id for entity-based rankings
CREATE INDEX IF NOT EXISTS idx_ppmm_entity_id 
    ON page_posts_metrics_mv (entity_id);

-- Composite index for entity + date queries (common in rankings)
CREATE INDEX IF NOT EXISTS idx_ppmm_entity_date 
    ON page_posts_metrics_mv (entity_id, recorded_at DESC);

-- Composite index for filtered queries (platform + date + to_scrape)
CREATE INDEX IF NOT EXISTS idx_ppmm_platform_date_scrape 
    ON page_posts_metrics_mv (platform, recorded_at DESC) 
    WHERE to_scrape = true;

-- Index on to_scrape for filtering active entities
CREATE INDEX IF NOT EXISTS idx_ppmm_to_scrape 
    ON page_posts_metrics_mv (to_scrape) 
    WHERE to_scrape = true;


-- =============================================================================
-- Verify Indexes
-- =============================================================================
-- Run this query to verify all indexes are created:
-- SELECT indexname, indexdef 
-- FROM pg_indexes 
-- WHERE tablename = 'page_posts_metrics_mv' 
-- ORDER BY indexname;
