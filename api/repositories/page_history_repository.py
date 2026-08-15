# Data-access methods for page history repository.
from api import db
from api.models import PageHistory
from api.models.category_model import Category
from api.models.entity_category_model import EntityCategory
from api.models.entity_model import Entity
from api.models.page_model import Page
from sqlalchemy import case, select, and_, cast, text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased
from api.utils.logging_utils import instrument_repository_class
from datetime import date, datetime, time, timedelta
import json
import os
from uuid import UUID

RootCategory = aliased(Category, name="root_category")

RANKING_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'ranking_cache.json')


class _UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


@instrument_repository_class
class PageHistoryRepository:
    @staticmethod
    def _followers_case(page_alias=Page, history_alias=PageHistory):
        return case(
            (page_alias.platform == "youtube", history_alias.data["subscribers"].astext),
            (page_alias.platform == "facebook", history_alias.data["page_followers"].astext),
            else_=history_alias.data["followers"].astext,
        )

    @staticmethod
    def _profile_url_case(page_alias=Page, history_alias=PageHistory):
        return case(
            (page_alias.platform == "youtube", history_alias.data["profile_image"]),
            (page_alias.platform == "x", history_alias.data["profile_image_link"]),
            (page_alias.platform == "tiktok", history_alias.data["profile_pic_url"]),
            (page_alias.platform == "linkedin", history_alias.data["logo"]),
            (page_alias.platform == "instagram", history_alias.data["profile_image_link"]),
        )

    @staticmethod
    def _description_case(page_alias=Page, history_alias=PageHistory):
        return case(
            (page_alias.platform == "youtube", history_alias.data["Description"]),
            (page_alias.platform == "x", history_alias.data["biography"]),
            (page_alias.platform == "tiktok", history_alias.data["biography"]),
            (page_alias.platform == "linkedin", history_alias.data["about"]),
            (page_alias.platform == "instagram", history_alias.data["biography"]),
        )

    @staticmethod
    def _posts_case(page_alias=Page, history_alias=PageHistory):
        empty_json_array = cast(text("'[]'"), JSONB)
        return case(
            (page_alias.platform == "instagram", db.func.coalesce(db.func.jsonb_path_query_array(history_alias.data, '$.posts'), empty_json_array)),
            (page_alias.platform == "linkedin", db.func.coalesce(db.func.jsonb_path_query_array(history_alias.data, '$.updates'), empty_json_array)),
            (page_alias.platform == "tiktok", db.func.coalesce(db.func.jsonb_path_query_array(history_alias.data, '$.top_videos'), empty_json_array)),
            (page_alias.platform == "youtube", db.func.coalesce(db.func.jsonb_path_query_array(history_alias.data, '$.top_videos'), empty_json_array)),
            (page_alias.platform == "x", db.func.coalesce(db.func.jsonb_path_query_array(history_alias.data, '$.posts'), empty_json_array)),
            else_=empty_json_array,
        )

    @staticmethod
    def _latest_history_subquery():
        return (
            select(
                PageHistory.page_id,
                db.func.max(PageHistory.id).label("latest_id"),
            )
            .group_by(PageHistory.page_id)
            .subquery()
        )

    @staticmethod
    def get_by_id(history_id: int) -> PageHistory | None:
        return PageHistory.query.get(history_id)

    @staticmethod
    def get_all() -> list[PageHistory]:
        return PageHistory.query.all()

    @staticmethod
    def create(page_id: int, data: dict) -> PageHistory:
        history = PageHistory(page_id=page_id, data=data)
        db.session.add(history)
        db.session.commit()
        return history

    @staticmethod
    def delete(history_id: int) -> bool:
        history = PageHistory.query.get(history_id)
        if not history:
            return False
        db.session.delete(history)
        db.session.commit()
        return True

    @staticmethod
    def get_today_all() -> list[PageHistory]:
        today = date.today()
        return db.session.scalars(
            select(PageHistory).where(db.func.date(PageHistory.recorded_at) == today)
        ).all()
    
    @staticmethod
    def get_followers_history_by_entity(entity_id: int):
        followers_case = PageHistoryRepository._followers_case().cast(db.Integer).label("followers")

        stmt = (
            select(
                PageHistory.recorded_at,
                followers_case,
                PageHistory.page_id,
                Page.platform
            )
            .join(Page, PageHistory.page_id == Page.uuid)
            .where(Page.entity_id == entity_id)
            .order_by(PageHistory.recorded_at)
        )

        return db.session.execute(stmt).all()

    @staticmethod
    def get_entity_likes_development(entity_id: int, date_limit: date):
        query = text("""
            SELECT
                entity_id,
                entity_name,
                page_id,
                platform,
                recorded_at,
                posts_metrics
            FROM page_posts_metrics_mv
            WHERE entity_id = :entity_id
              AND platform IN ('instagram','linkedin','tiktok','x','facebook')
              AND date(recorded_at) >= :date_limit
              AND to_scrape
            ORDER BY page_id, platform, recorded_at ASC
        """)
        return db.session.execute(query, {"entity_id": entity_id, "date_limit": date_limit}).all()

    @staticmethod
    def get_entities_likes_development(entity_ids: list[int], date_limit: date):
        if not entity_ids:
            return []

        query = text("""
            SELECT
                entity_id,
                entity_name,
                page_id,
                platform,
                recorded_at,
                posts_metrics
            FROM page_posts_metrics_mv
            WHERE entity_id IN :entity_ids
              AND platform IN ('instagram','linkedin','tiktok','x','facebook')
              AND date(recorded_at) >= :date_limit
              AND to_scrape
            ORDER BY entity_name, page_id, platform, recorded_at ASC
        """).bindparams(bindparam("entity_ids", expanding=True))

        return db.session.execute(query, {"entity_ids": entity_ids, "date_limit": date_limit}).all()

    @staticmethod
    def get_entity_comments_development(entity_id: int, date_limit: date):
        query = text("""
            SELECT
                entity_id,
                entity_name,
                page_id,
                platform,
                recorded_at,
                posts_metrics
            FROM page_posts_metrics_mv
            WHERE entity_id = :entity_id
              AND platform IN ('instagram','linkedin','tiktok','x','facebook')
              AND date(recorded_at) >= :date_limit
              AND to_scrape
            ORDER BY page_id, platform, recorded_at ASC
        """)
        return db.session.execute(query, {"entity_id": entity_id, "date_limit": date_limit}).all()

    @staticmethod
    def get_entities_comments_development(entity_ids: list[int], date_limit: date):
        if not entity_ids:
            return []

        query = text("""
            SELECT
                entity_id,
                entity_name,
                page_id,
                platform,
                recorded_at,
                posts_metrics
            FROM page_posts_metrics_mv
            WHERE entity_id IN :entity_ids
              AND platform IN ('instagram','linkedin','tiktok','x','facebook')
              AND date(recorded_at) >= :date_limit
              AND to_scrape
            ORDER BY entity_name, page_id, platform, recorded_at ASC
        """).bindparams(bindparam("entity_ids", expanding=True))

        return db.session.execute(query, {"entity_ids": entity_ids, "date_limit": date_limit}).all()
    
    @staticmethod
    def get_entity_posts__old(entity_id: int):

        subq = (
            select(
                PageHistory.id.label("hist_id"),
                PageHistory.page_id,
                PageHistory.recorded_at,
                db.func.date(PageHistory.recorded_at).label("day")
            )
            .join(Page, PageHistory.page_id == Page.uuid)
            .where(Page.entity_id == entity_id)
            .order_by(
                PageHistory.page_id,
                db.func.date(PageHistory.recorded_at),
                PageHistory.recorded_at.desc()
            )
            .distinct(
                PageHistory.page_id,
                db.func.date(PageHistory.recorded_at)
            )
            .subquery()
        )

        stmt = (
            select(
                Page.uuid.label("page_id"),
                Page.name.label("page_name"),
                Page.platform,
                PageHistory.recorded_at,
                PageHistoryRepository._posts_case().label("posts"),
                Page.entity_id.label("entity_id")
            )
            .join(subq, subq.c.hist_id == PageHistory.id)
            .join(Page, PageHistory.page_id == Page.uuid)
            .order_by(PageHistory.recorded_at.desc())
        )

        return db.session.execute(stmt).all()
    

    @staticmethod
    def get_entity_posts_new(entity_id: int, date_limit: date = None, max_posts: int = None):
        query = text("""
            SELECT *
            FROM page_posts_metrics_mv
            WHERE entity_id = :entity_id
            AND platform IN ('instagram','linkedin','tiktok','youtube','x','facebook')
            AND  date(recorded_at) >= :date_limit
            AND to_scrape
            ORDER BY recorded_at DESC
            LIMIT :max_posts
                """)

        results = db.session.execute(query, {'entity_id': entity_id, 'date_limit': date_limit, 'max_posts': max_posts}).all()
        return results


    @staticmethod
    def refresh_metrics_mv():
        """
        Refresh the page_posts_metrics_mv materialized view so API reads reflect
        the latest scraped pages_history rows.

        The scraper loads pages_history out-of-band; without this refresh the MV
        stays frozen on an old snapshot, which is why profile image URLs (signed
        + short-lived) expire and recent-window rankings return no data. Call
        this right after each daily scrape (see `flask refresh-mv`).

        Tries CONCURRENTLY first (non-blocking; needs the unique index
        idx_ppmm_unique and an already-populated view). Falls back to a plain
        REFRESH if CONCURRENTLY isn't possible (e.g. first populate).
        """
        try:
            db.session.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY page_posts_metrics_mv")
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            db.session.execute(
                text("REFRESH MATERIALIZED VIEW page_posts_metrics_mv")
            )
            db.session.commit()

    @staticmethod
    def get_all_entities_posts(date_limit, entity_type=None):
        # `entity_type` restricts the posts to one entity kind ('company' /
        # 'influencer'), so the posts rankings can be split the same way the
        # entity rankings already are. None keeps the original behavior of
        # returning every entity's posts mixed together.
        #
        # The MV carries no entity type of its own, so the kind comes from the
        # `entities` table — the same join `get_companies_interactions_summary`
        # uses. `mv.*` is preserved so callers keep reading the same columns.
        params = {'date_limit': date_limit}

        if entity_type:
            query = text("""
                SELECT mv.* from page_posts_metrics_mv mv
                JOIN entities e ON e.id = mv.entity_id
                where mv.platform in ('instagram','linkedin','tiktok','youtube','x', 'facebook')
                and date(mv.recorded_at) >= :date_limit
                and mv.to_scrape
                and LOWER(COALESCE(e.type, '')) = :entity_type
                        """)
            params['entity_type'] = entity_type.lower()
        else:
            query = text("""
                SELECT * from page_posts_metrics_mv
                where platform in ('instagram','linkedin','tiktok','youtube','x', 'facebook')
                and date(recorded_at) >= :date_limit
                and to_scrape
                        """)

        results = db.session.execute(query, params).all()
        return results

    @staticmethod
    def get_entities_followers_snapshot(date_limit):
        """
        Returns per page:
          - current_followers : from the most recent recording ever
          - prev_followers    : from the oldest recording within the last-30-day window
                                (i.e. the snapshot closest to `date_limit`)
        """
        query = text("""
            WITH latest AS (
                SELECT DISTINCT ON (page_id)
                    page_id,
                    raw_followers AS current_followers
                FROM page_posts_metrics_mv
                WHERE platform IN ('instagram','linkedin','tiktok','youtube','x', 'facebook')
                  AND to_scrape
                ORDER BY page_id, recorded_at DESC
            ),
            prev AS (
                SELECT DISTINCT ON (page_id)
                    page_id,
                    raw_followers AS prev_followers
                FROM page_posts_metrics_mv
                WHERE platform IN ('instagram','linkedin','tiktok','youtube','x', 'facebook')
                  AND to_scrape
                  AND date(recorded_at) >= :date_limit
                ORDER BY page_id, recorded_at ASC
            )
            SELECT
                l.page_id,
                l.current_followers,
                p.prev_followers
            FROM latest l
            LEFT JOIN prev p ON p.page_id = l.page_id
        """)
        results = db.session.execute(query, {'date_limit': date_limit}).all()
        return results

    @staticmethod
    def get_followers_progress_snapshot(date_limit, end_date=None, entity_type=None):
        # `entity_type` (e.g. 'influencer') optionally restricts the ranking to a
        # single entity kind; when None, every entity type is included as before.
        query = text("""
            WITH latest AS (
                SELECT DISTINCT ON (page_id)
                    page_id,
                    entity_id,
                    entity_name,
                    platform,
                    page_name,
                    page_url,
                    profile_url AS profile_image_url,
                    category,
                    root_category,
                    raw_followers AS current_followers
                FROM page_posts_metrics_mv
                WHERE platform IN ('instagram','linkedin','tiktok','youtube','x', 'facebook')
                  AND raw_followers IS NOT NULL
                  AND to_scrape
                  AND (:end_date IS NULL OR date(recorded_at) <= :end_date)
                ORDER BY page_id, recorded_at DESC
            ),
            prev AS (
                SELECT DISTINCT ON (page_id)
                    page_id,
                    raw_followers AS prev_followers
                FROM page_posts_metrics_mv
                WHERE platform IN ('instagram','linkedin','tiktok','youtube','x', 'facebook')
                  AND raw_followers IS NOT NULL
                  AND to_scrape
                  AND date(recorded_at) >= :date_limit
                  AND (:end_date IS NULL OR date(recorded_at) <= :end_date)
                ORDER BY page_id, recorded_at ASC
            )
            SELECT
                l.page_id,
                l.entity_id,
                l.entity_name,
                e.type AS entity_type,
                l.platform,
                l.page_name,
                l.page_url,
                l.profile_image_url,
                l.category,
                l.root_category,
                l.current_followers,
                p.prev_followers
            FROM latest l
            JOIN entities e ON e.id = l.entity_id
            LEFT JOIN prev p ON p.page_id = l.page_id
            WHERE (:entity_type IS NULL OR LOWER(COALESCE(e.type, '')) = :entity_type)
        """)
        params = {
            'date_limit': date_limit,
            'end_date': end_date,
            'entity_type': entity_type.lower() if entity_type else None,
        }
        results = db.session.execute(query, params).mappings().all()
        return results



    @staticmethod
    def get_companies_interactions_summary(date_limit: date = None, end_date: date = None, entity_type: str = "company"):
        # `entity_type` selects which entity kind to summarize (default 'company'
        # preserves the original company-only behavior; pass 'influencer' etc.).
        if date_limit is None:
            date_limit = (datetime.now() - timedelta(days=30)).date()

        query = text("""
            WITH page_entity_map AS (
                SELECT DISTINCT ON (page_id)
                    page_id,
                    entity_id,
                    entity_name,
                    page_name,
                    page_url,
                    profile_url AS profile_image_url,
                    to_scrape
                FROM page_posts_metrics_mv
                ORDER BY page_id, recorded_at DESC
            ),
            entity_category_map AS (
                SELECT
                    entity_id,
                    MIN(category) AS category,
                    MIN(root_category) AS root_category
                FROM page_posts_metrics_mv
                GROUP BY entity_id
            )
            SELECT
                pem.entity_id AS entity_id,
                pem.entity_name AS entity_name,
                ecm.category AS category,
                ecm.root_category AS root_category,
                pm.platform AS platform,
                pm.page_id AS page_id,
                pem.page_name AS page_name,
                pem.page_url AS page_url,
                pem.profile_image_url AS profile_image_url,
                COUNT(pm.post_id) AS posts_count,
                COALESCE(SUM(pm.likes), 0)::BIGINT AS total_likes,
                COALESCE(SUM(pm.comments), 0)::BIGINT AS total_comments,
                COALESCE(SUM(pm.shares), 0)::BIGINT AS total_shares,
                COALESCE(SUM(pm.views), 0)::BIGINT AS total_views
            FROM posts_mv pm
            JOIN page_entity_map pem ON pem.page_id = pm.page_id
            JOIN entities e ON e.id = pem.entity_id
            LEFT JOIN entity_category_map ecm ON ecm.entity_id = pem.entity_id
            WHERE LOWER(COALESCE(e.type, '')) = :entity_type
              AND pem.to_scrape
              AND e.to_scrape
              AND pm.platform IN ('instagram','linkedin','tiktok','youtube','x', 'facebook')
              AND DATE(pm.created_at) >= :date_limit
              AND (:end_date IS NULL OR DATE(pm.created_at) <= :end_date)
                        GROUP BY pem.entity_id, pem.entity_name, ecm.category, ecm.root_category, pm.platform, pm.page_id, pem.page_name, pem.page_url, pem.profile_image_url
            ORDER BY pem.entity_name, pm.platform
        """)

        params = {
            'date_limit': date_limit,
            'end_date': end_date,
            'entity_type': (entity_type or "company").lower(),
        }
        return db.session.execute(query, params).mappings().all()




    @staticmethod
    def get_page_posts(page_id: int):

        stmt = (
            select(
                Page.uuid.label("page_id"),
                Page.name.label("page_name"),
                Page.platform,
                PageHistory.recorded_at,
                PageHistoryRepository._posts_case().label("posts")
            )
            .join(Page, PageHistory.page_id == Page.uuid)
            
            .where(Page.uuid == page_id)
        )

        return db.session.execute(stmt).all()
        
    @staticmethod
    def get_entity_info_from_history(entity_id: int):
        # Optimized version using materialized view for fast lookups
        # Falls back to PageHistory table for missing fields (description)
        # This resolves 504 timeout issues for entities with many pages
        query = text("""
            WITH latest_pages_mv AS (
                -- Get the latest snapshot from materialized view (fast)
                SELECT DISTINCT ON (page_id)
                    page_id,
                    history_id,
                    entity_name,
                    platform,
                    page_name,
                    page_url,
                    profile_url,
                    raw_followers,
                    recorded_at
                FROM page_posts_metrics_mv
                WHERE entity_id = :entity_id
                  AND to_scrape
                  AND raw_followers IS NOT NULL
                  AND raw_followers != 0
                ORDER BY page_id, recorded_at DESC
            ),
            page_descriptions AS (
                -- Get description from pages_history for each page
                -- Try latest snapshot first, fall back to older if missing
                SELECT DISTINCT ON (lp.page_id)
                    lp.page_id,
                    CASE
                        WHEN lp.platform = 'youtube' THEN ph.data->>'Description'
                        WHEN lp.platform = 'x' THEN ph.data->>'biography'
                        WHEN lp.platform = 'tiktok' THEN ph.data->>'biography'
                        WHEN lp.platform = 'linkedin' THEN ph.data->>'about'
                        WHEN lp.platform = 'instagram' THEN ph.data->>'biography'
                        WHEN lp.platform = 'facebook' THEN ph.data->>'page_about'
                        ELSE NULL
                    END AS description
                FROM latest_pages_mv lp
                JOIN pages_history ph ON ph.page_id = lp.page_id
                WHERE ph.recorded_at <= lp.recorded_at
                  AND (
                      (lp.platform = 'youtube' AND ph.data->>'Description' IS NOT NULL AND ph.data->>'Description' != '')
                      OR (lp.platform = 'x' AND ph.data->>'biography' IS NOT NULL AND ph.data->>'biography' != '')
                      OR (lp.platform = 'tiktok' AND ph.data->>'biography' IS NOT NULL AND ph.data->>'biography' != '')
                      OR (lp.platform = 'linkedin' AND ph.data->>'about' IS NOT NULL AND ph.data->>'about' != '')
                      OR (lp.platform = 'instagram' AND ph.data->>'biography' IS NOT NULL AND ph.data->>'biography' != '')
                      OR (lp.platform = 'facebook' AND ph.data->>'page_about' IS NOT NULL AND ph.data->>'page_about' != '')
                  )
                ORDER BY lp.page_id, ph.recorded_at DESC
            ),
            entity_total AS (
                SELECT 
                    COALESCE(SUM(raw_followers), 0)::BIGINT AS total_followers
                FROM latest_pages_mv
            ),
            all_entities_totals AS (
                SELECT DISTINCT ON (entity_id)
                    entity_id,
                    SUM(raw_followers) OVER (PARTITION BY entity_id)::BIGINT AS entity_total_followers
                FROM (
                    SELECT DISTINCT ON (entity_id, page_id)
                        entity_id,
                        page_id,
                        raw_followers
                    FROM page_posts_metrics_mv
                    WHERE to_scrape
                      AND raw_followers IS NOT NULL
                      AND raw_followers != 0
                    ORDER BY entity_id, page_id, recorded_at DESC
                ) latest_entity_pages
            ),
            entity_rank AS (
                SELECT COALESCE(COUNT(*) + 1, 1)::INTEGER AS rank
                FROM all_entities_totals
                WHERE entity_total_followers > (SELECT total_followers FROM entity_total)
            )
            SELECT
                lp.page_id,
                lp.platform,
                lp.page_name AS name,
                lp.page_url AS link,
                lp.entity_name,
                :entity_id AS entity_id,
                et.total_followers,
                er.rank AS entity_rank,
                lp.profile_url,
                COALESCE(pd.description, '') AS description,
                lp.raw_followers AS followers
            FROM latest_pages_mv lp
            LEFT JOIN page_descriptions pd ON pd.page_id = lp.page_id
            CROSS JOIN entity_total et
            CROSS JOIN entity_rank er
            ORDER BY lp.platform, lp.page_id
        """)
        
        rows = db.session.execute(query, {"entity_id": entity_id}).all()

        if len(rows) < 1:
            return []
        
        # Get entity type from entities table
        entity = db.session.get(Entity, entity_id)
        entity_type = entity.type if entity else None
        
        result = {
            "entity_name": rows[0].entity_name,
            "entity_id": rows[0].entity_id,
            "type": entity_type,
            "total_followers": rows[0].total_followers,
            "rank": rows[0].entity_rank,
            "pages": {}
        }

        # Track platforms to handle multiple pages per platform
        platform_page_counts = {}

        for row in rows:
            platform = row.platform
            # Track how many pages we've seen for this platform
            if platform not in platform_page_counts:
                platform_page_counts[platform] = 0
            platform_page_counts[platform] += 1
            
            # Use platform name for first page, platform_pageId for additional pages
            if platform_page_counts[platform] == 1:
                page_key = platform
            else:
                # For additional pages, append page_id to make key unique
                page_key = f"{platform}_{row.page_id}"
                # Also rename the first page's key to include its page_id
                if platform_page_counts[platform] == 2:
                    # Find and rename the first page entry
                    old_entry = result["pages"].pop(platform)
                    first_page_id = old_entry.get("page_id", "1")
                    result["pages"][f"{platform}_{first_page_id}"] = old_entry

            result["pages"][page_key] = {
                "page_id": row.page_id,
                "followers": row.followers,
                "profile_url": row.profile_url,
                "description": row.description,
                "page_url": row.link,
            }

        return result
    
    @staticmethod
    def get_entites_followers_competition(entities):
        OtherEntity = aliased(Entity)   # alias for the second Entity join
        entities_history_stmt = (
            select(
                OtherEntity.name.label("entity_name"),
                OtherEntity.id.label("entity_id"),
                PageHistory.recorded_at,
                cast(db.func.coalesce(PageHistoryRepository._followers_case(), "0"), db.Integer).label("followers"),
                PageHistory.page_id,
                Page.platform
            )
            .join(Page, PageHistory.page_id == Page.uuid)
            .join(OtherEntity, OtherEntity.id == Page.entity_id)
            .where(Page.entity_id.in_(entities))
            .order_by(OtherEntity.name, PageHistory.recorded_at)
        )
        results = db.session.execute(entities_history_stmt).mappings().all()
        return results
        
    @staticmethod
    def get_category_followers_competition(entity_id):
        EntityCategory2 = aliased(EntityCategory)
        OtherEntity = aliased(Entity)   # alias for the second Entity join

        similar_entities_stmt = (
            select(OtherEntity.id)  # we want the ID of the similar entity
            .select_from(Entity)
            .join(EntityCategory, EntityCategory.entity_id == Entity.id)  # categories of base entity
            .join(EntityCategory2, EntityCategory2.category_id == EntityCategory.category_id)  # same categories
            .join(OtherEntity, EntityCategory2.entity_id == OtherEntity.id)  # similar entities
            .where(EntityCategory.entity_id == entity_id)  # filter to given entity
            .distinct()

        )
        similar_entities = db.session.scalars(similar_entities_stmt).all()
        # print(similar_entities)
        entities_history_stmt = (
            select(
                OtherEntity.name.label("entity_name"),
                OtherEntity.id.label("entity_id"),
                PageHistory.recorded_at,
                PageHistoryRepository._followers_case().cast(db.Integer).label("followers"),
                PageHistory.page_id,
                Page.platform
            )
            .join(Page, PageHistory.page_id == Page.uuid)
            .join(OtherEntity, OtherEntity.id == Page.entity_id)
            .where(Page.entity_id.in_(similar_entities))
            .order_by(OtherEntity.name, PageHistory.recorded_at)
        )
        results = db.session.execute(entities_history_stmt).mappings().all()
        return results
        
    @staticmethod
    def get_all_entities_ranking_by_date(target_date: date):
        # Build a per-page snapshot for the target date, interpolating when the day is missing.
        query = text("""
            WITH base AS (
                SELECT
                    page_id,
                    entity_id,
                    entity_name,
                    platform,
                    page_name,
                    page_url,
                    profile_url AS profile_image_url,
                    category,
                    raw_followers::BIGINT AS followers,
                    DATE(recorded_at) AS snapshot_date,
                    recorded_at
                FROM page_posts_metrics_mv
                WHERE platform IN ('instagram','linkedin','tiktok','youtube','x', 'facebook')
                  AND raw_followers IS NOT NULL
                  AND to_scrape
            ),
            prev_day AS (
                SELECT DISTINCT ON (page_id)
                    page_id,
                    entity_id,
                    entity_name,
                    platform,
                    page_name,
                    page_url,
                    profile_image_url,
                    category,
                    followers,
                    snapshot_date
                FROM base
                WHERE snapshot_date <= :target_date
                ORDER BY page_id, snapshot_date DESC, recorded_at DESC
            ),
            next_day AS (
                SELECT DISTINCT ON (page_id)
                    page_id,
                    entity_id,
                    entity_name,
                    platform,
                    page_name,
                    page_url,
                    profile_image_url,
                    category,
                    followers,
                    snapshot_date
                FROM base
                WHERE snapshot_date >= :target_date
                ORDER BY page_id, snapshot_date ASC, recorded_at ASC
            ),
            resolved_page_data AS (
                SELECT
                    COALESCE(prev_day.page_id, next_day.page_id) AS page_id,
                    COALESCE(prev_day.entity_id, next_day.entity_id) AS entity_id,
                    COALESCE(prev_day.entity_name, next_day.entity_name) AS entity_name,
                    COALESCE(prev_day.platform, next_day.platform) AS platform,
                    COALESCE(prev_day.page_name, next_day.page_name) AS page_name,
                    COALESCE(prev_day.page_url, next_day.page_url) AS page_url,
                    COALESCE(prev_day.profile_image_url, next_day.profile_image_url) AS profile_image_url,
                    COALESCE(prev_day.category, next_day.category) AS category,
                    CASE
                        WHEN prev_day.snapshot_date = :target_date THEN prev_day.followers
                        WHEN next_day.snapshot_date = :target_date THEN next_day.followers
                        WHEN prev_day.followers IS NOT NULL AND next_day.followers IS NOT NULL
                            THEN ROUND((prev_day.followers + next_day.followers) / 2.0)::BIGINT
                        ELSE COALESCE(prev_day.followers, next_day.followers)
                    END AS followers
                FROM prev_day
                FULL OUTER JOIN next_day ON next_day.page_id = prev_day.page_id
            ),
            entity_category_map AS (
                SELECT
                    entity_id,
                    MIN(category) AS category
                FROM resolved_page_data
                GROUP BY entity_id
            ),
            entity_totals AS (
                SELECT
                    entity_id,
                    SUM(followers)::BIGINT AS total_followers,
                    CAST(:target_date AS DATE) AS window_start,
                    RANK() OVER (ORDER BY SUM(followers) DESC) AS entity_rank
                FROM resolved_page_data
                WHERE followers IS NOT NULL
                GROUP BY entity_id
            )
            SELECT
                rpd.entity_id,
                rpd.entity_name,
                et.total_followers,
                et.entity_rank,
                et.window_start,
                ecm.category,
                rpd.platform,
                rpd.page_name,
                rpd.page_id,
                rpd.page_url,
                rpd.profile_image_url,
                rpd.followers
            FROM resolved_page_data rpd
            JOIN entity_totals et ON et.entity_id = rpd.entity_id
            LEFT JOIN entity_category_map ecm ON ecm.entity_id = rpd.entity_id
            WHERE rpd.followers IS NOT NULL
            ORDER BY et.entity_rank, rpd.platform
        """)

        rows = db.session.execute(query, {"target_date": target_date}).mappings().all()
        if len(rows) < 1:
            return []

        result = {}
        for row in rows:
            entity_id = row["entity_id"]
            if entity_id not in result:
                result[entity_id] = {
                    "entity_id": entity_id,
                    "entity_name": row["entity_name"],
                    "total_followers": row["total_followers"],
                    "rank": row["entity_rank"],
                    "category": row["category"],
                    "root_category": row["category"],
                    "window_start": row["window_start"].isoformat() if row["window_start"] else None,
                    "platforms": {}
                }

            result[entity_id]["platforms"][row["platform"]] = {
                "page_name": row["page_name"],
                "page_id": row["page_id"],
                "followers": row["followers"],
                "profile_image_url": row["profile_image_url"],
                "page_url": row["page_url"],
            }

        return sorted(result.values(), key=lambda x: x["rank"])

    @staticmethod
    def get_all_entities_ranking():
        if db.engine.dialect.name == 'sqlite':
            return []
        query = text("""
            WITH latest_page_data AS (
                SELECT DISTINCT ON (page_id)
                    page_id,
                    entity_id,
                    entity_name,
                    platform,
                    page_name,
                    page_url,
                    profile_url AS profile_image_url,
                    category,
                    raw_followers::BIGINT AS followers,
                    DATE(recorded_at) AS snapshot_date
                FROM page_posts_metrics_mv
                WHERE platform IN ('instagram','linkedin','tiktok','youtube','x', 'facebook')
                  AND raw_followers IS NOT NULL
                  AND to_scrape
                ORDER BY page_id, recorded_at DESC
            ),
            entity_category_map AS (
                SELECT
                    entity_id,
                    MIN(category) AS category
                FROM latest_page_data
                GROUP BY entity_id
            ),
            entity_totals AS (
                SELECT
                    entity_id,
                    SUM(followers)::BIGINT AS total_followers,
                    MIN(snapshot_date) AS window_start,
                    RANK() OVER (ORDER BY SUM(followers) DESC) AS entity_rank
                FROM latest_page_data
                GROUP BY entity_id
            )
            SELECT
                lpd.entity_id,
                lpd.entity_name,
                e.type AS entity_type,
                et.total_followers,
                et.entity_rank,
                et.window_start,
                ecm.category,
                lpd.platform,
                lpd.page_name,
                lpd.page_id,
                lpd.page_url,
                lpd.profile_image_url,
                lpd.followers
            FROM latest_page_data lpd
            JOIN entity_totals et ON et.entity_id = lpd.entity_id
            JOIN entities e ON e.id = lpd.entity_id
            LEFT JOIN entity_category_map ecm ON ecm.entity_id = lpd.entity_id
            ORDER BY et.entity_rank, lpd.platform
        """)

        rows = db.session.execute(query).mappings().all()
        if len(rows) < 1:
            return []
        
        # --- Step 4: Build result dict ---
        result = {}
        for row in rows:
            entity_id = row["entity_id"]
            if entity_id not in result:
                result[entity_id] = {
                    "entity_id": entity_id,
                    "entity_name": row["entity_name"],
                    "type": row["entity_type"],
                    "total_followers": row["total_followers"],
                    "rank": row["entity_rank"],
                    "category": row["category"],
                    "root_category": row["category"],
                    "window_start": row["window_start"].isoformat() if row["window_start"] else None,
                    "platforms": {}
                }

            result[entity_id]["platforms"][row["platform"]] = {
                "page_name": row["page_name"],
                "page_id": row["page_id"],
                "followers": row["followers"],
                "profile_image_url": row["profile_image_url"],
                "page_url": row["page_url"],
            }

        # return list sorted by rank
        return sorted(result.values(), key=lambda x: x["rank"])

    @staticmethod
    def get_page_data_today(page_id) -> list["PageHistory"]:
        today = date.today()
        return db.session.scalars(
            select(PageHistory).where(
                and_(
                    db.func.date(PageHistory.recorded_at) == today,
                    PageHistory.page_id == page_id
                )
            )
        ).all()
    
    @staticmethod
    def get_entity_data_by_date( entity_id: int, target_date: date):
        stmt = (
            select(PageHistory)
            .join(Page, Page.uuid == PageHistory.page_id)
            .where(
                and_(
                    Page.entity_id == entity_id,
                    db.func.date(PageHistory.recorded_at) == target_date
                )
            )
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_after_time(hour):
        # Build today 22:00 timestamp
        today = datetime.now().date() - timedelta(days=1)
        time_threshold = datetime.combine(today, time(hour, 0))

        stmt = (
            select(PageHistory)
            .where(PageHistory.recorded_at > time_threshold)
        )
        return db.session.scalars(stmt).all()
    
    @staticmethod
    def get_platform_history(platform: str):
        stmt =( select(PageHistory)
            .join(Page, PageHistory.page_id == Page.uuid)
            .filter(Page.platform == platform)
        )
            
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_public_ranking():
        """
        Returns the cached monthly ranking from file. Recomputes only when the month changes.
        """
        now = datetime.now()
        current_month = f"{now.year}-{now.month:02d}"

        # Try reading from cache file
        if os.path.exists(RANKING_CACHE_FILE):
            try:
                with open(RANKING_CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                cached_data = cache.get("data")
                # Ignore caches written before the `type` field existed so the
                # public influencer filter has something to match on.
                cache_has_type = (
                    isinstance(cached_data, list)
                    and cached_data
                    and "type" in cached_data[0]
                )
                if cache.get("month") == current_month and cache_has_type:
                    return cached_data
            except (json.JSONDecodeError, KeyError):
                pass

        # Recompute and save
        data = PageHistoryRepository.get_all_entities_ranking()
        with open(RANKING_CACHE_FILE, 'w') as f:
            json.dump({"month": current_month, "data": data}, f, cls=_UUIDEncoder)
        return data

    @staticmethod
    def get_pages_history_filtered(
        start_date=None,
        end_date=None,
        brand_id=None,
        brand_name=None,
        platform=None,
        page_id=None,
        search=None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "recorded_at",
        sort_order: str = "desc",
        include_data: bool = True
    ):
        query = (
            select(
                PageHistory.id,
                PageHistory.page_id,
                PageHistory.recorded_at,
                PageHistory.data,
                Page.name.label("page_name"),
                Page.link.label("page_link"),
                Page.platform,
                Entity.id.label("brand_id"),
                Entity.name.label("brand_name")
            )
            .join(Page, PageHistory.page_id == Page.uuid)
            .join(Entity, Page.entity_id == Entity.id)
        )

        conditions = []
        if start_date:
            conditions.append(PageHistory.recorded_at >= start_date)
        if end_date:
            conditions.append(PageHistory.recorded_at <= end_date)
        if brand_id is not None:
            conditions.append(Entity.id == brand_id)
        if brand_name:
            conditions.append(Entity.name.ilike(f"%{brand_name.strip()}%"))
        if platform:
            if isinstance(platform, (list, tuple)):
                conditions.append(Page.platform.in_([p.strip().lower() for p in platform]))
            else:
                conditions.append(Page.platform == platform.strip().lower())
        if page_id:
            conditions.append(PageHistory.page_id == page_id)
        if search:
            term = f"%{search.strip()}%"
            conditions.append(
                db.or_(
                    Page.name.ilike(term),
                    Entity.name.ilike(term),
                    Page.link.ilike(term)
                )
            )

        if conditions:
            query = query.where(and_(*conditions))

        # Count total before pagination
        count_stmt = select(db.func.count()).select_from(query.subquery())
        total = db.session.scalar(count_stmt) or 0

        # Sorting
        sort_column = getattr(PageHistory, sort_by, PageHistory.recorded_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc(), PageHistory.id.asc())
        else:
            query = query.order_by(sort_column.desc(), PageHistory.id.desc())

        # Pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        results = db.session.execute(query).all()

        items = []
        for r in results:
            item = {
                "id": r.id,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "page_id": str(r.page_id) if r.page_id else None,
                "page_name": r.page_name,
                "page_link": r.page_link,
                "platform": r.platform,
                "brand_id": r.brand_id,
                "brand_name": r.brand_name,
            }
            if include_data:
                item["data"] = r.data
            items.append(item)

        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }

    @staticmethod
    def get_pages_history_by_id(history_id: int):
        stmt = (
            select(
                PageHistory.id,
                PageHistory.page_id,
                PageHistory.recorded_at,
                PageHistory.data,
                Page.name.label("page_name"),
                Page.link.label("page_link"),
                Page.platform,
                Entity.id.label("brand_id"),
                Entity.name.label("brand_name")
            )
            .join(Page, PageHistory.page_id == Page.uuid)
            .join(Entity, Page.entity_id == Entity.id)
            .where(PageHistory.id == history_id)
        )
        result = db.session.execute(stmt).first()
        if not result:
            return None

        return {
            "id": result.id,
            "recorded_at": result.recorded_at.isoformat() if result.recorded_at else None,
            "page_id": str(result.page_id) if result.page_id else None,
            "page_name": result.page_name,
            "page_link": result.page_link,
            "platform": result.platform,
            "brand_id": result.brand_id,
            "brand_name": result.brand_name,
            "data": result.data
        }

    @staticmethod
    def get_pages_history_options():
        platforms_stmt = (
            select(Page.platform)
            .join(PageHistory, PageHistory.page_id == Page.uuid)
            .distinct()
            .order_by(Page.platform)
        )
        platforms = [p for p in db.session.scalars(platforms_stmt).all() if p]

        brands_stmt = (
            select(Entity.id, Entity.name)
            .join(Page, Page.entity_id == Entity.id)
            .join(PageHistory, PageHistory.page_id == Page.uuid)
            .distinct()
            .order_by(Entity.name)
        )
        brands_rows = db.session.execute(brands_stmt).all()
        brands = [{"id": b.id, "name": b.name} for b in brands_rows]

        dates_stmt = select(
            db.func.min(PageHistory.recorded_at).label("min_date"),
            db.func.max(PageHistory.recorded_at).label("max_date"),
            db.func.count(PageHistory.id).label("total_count")
        )
        dates_res = db.session.execute(dates_stmt).first()

        min_date = dates_res.min_date.isoformat() if dates_res and dates_res.min_date else None
        max_date = dates_res.max_date.isoformat() if dates_res and dates_res.max_date else None
        total_count = dates_res.total_count if dates_res else 0

        return {
            "platforms": platforms,
            "brands": brands,
            "date_range": {
                "min_date": min_date,
                "max_date": max_date
            },
            "total_records": total_count
        }

    @staticmethod
    def get_pages_history_summary():
        now = datetime.now()
        today_start = datetime.combine(now.date(), time.min)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        total = db.session.scalar(select(db.func.count(PageHistory.id))) or 0
        records_today = db.session.scalar(
            select(db.func.count(PageHistory.id)).where(PageHistory.recorded_at >= today_start)
        ) or 0
        records_7d = db.session.scalar(
            select(db.func.count(PageHistory.id)).where(PageHistory.recorded_at >= seven_days_ago)
        ) or 0
        records_30d = db.session.scalar(
            select(db.func.count(PageHistory.id)).where(PageHistory.recorded_at >= thirty_days_ago)
        ) or 0

        platform_counts_stmt = (
            select(Page.platform, db.func.count(PageHistory.id).label("count"))
            .join(PageHistory, PageHistory.page_id == Page.uuid)
            .group_by(Page.platform)
        )
        platform_rows = db.session.execute(platform_counts_stmt).all()
        by_platform = {r.platform: r.count for r in platform_rows if r.platform}

        distinct_pages = db.session.scalar(
            select(db.func.count(db.func.distinct(PageHistory.page_id)))
        ) or 0

        return {
            "total_records": total,
            "records_today": records_today,
            "records_last_7_days": records_7d,
            "records_last_30_days": records_30d,
            "by_platform": by_platform,
            "active_pages_monitored": distinct_pages
        }

