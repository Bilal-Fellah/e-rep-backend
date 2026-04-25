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
                db.func.max(PageHistory.recorded_at).label("latest_recorded_at"),
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
            AND platform IN ('instagram','linkedin','tiktok','youtube','x')
            AND  date(recorded_at) >= :date_limit
            AND to_scrape
            ORDER BY recorded_at DESC
            LIMIT :max_posts
                """)

        results = db.session.execute(query, {'entity_id': entity_id, 'date_limit': date_limit, 'max_posts': max_posts}).all()
        return results


    @staticmethod
    def get_all_entities_posts(date_limit):
        query = text("""
            SELECT * from page_posts_metrics_mv
            where platform in ('instagram','linkedin','tiktok','youtube','x', 'facebook')
            and date(recorded_at) >= :date_limit
            and to_scrape
                    """)
        results = db.session.execute(query, {'date_limit': date_limit}).all()
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
    def get_companies_interactions_summary(date_limit: date = None):
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
            WHERE LOWER(COALESCE(e.type, '')) = 'company'
              AND pem.to_scrape
              AND e.to_scrape
              AND pm.platform IN ('instagram','linkedin','tiktok','youtube','x', 'facebook')
              AND DATE(pm.created_at) >= :date_limit
                        GROUP BY pem.entity_id, pem.entity_name, ecm.category, ecm.root_category, pm.platform, pm.page_id, pem.page_name, pem.page_url, pem.profile_image_url
            ORDER BY pem.entity_name, pm.platform
        """)

        return db.session.execute(query, {'date_limit': date_limit}).mappings().all()



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
        latest_history_subq = PageHistoryRepository._latest_history_subquery()

        ph_alias = aliased(PageHistory)

        page_followers = PageHistoryRepository._followers_case(Page, ph_alias).cast(db.Integer)

        # Step 3: Aggregate per entity (total followers)
        entity_totals_subq = (
            select(
                Entity.id.label("entity_id"),
                db.func.sum(page_followers).label("total_followers"),
                db.func.rank()
                    .over(order_by=db.func.sum(page_followers).desc())
                    .label("entity_rank"),
            )
            .join(Page, Page.entity_id == Entity.id)
            .join(
                latest_history_subq,
                latest_history_subq.c.page_id == Page.uuid
            )
            .join(
                ph_alias,
                (ph_alias.page_id == Page.uuid)
                & (ph_alias.recorded_at == latest_history_subq.c.latest_recorded_at)
            )
            .group_by(Entity.id)
            .subquery()
        )

        # Step 4: Get entity + page info + join with totals
        stmt = (
            select(
                Page.uuid.label("page_id"),
                Page.platform,
                Page.name,
                Page.link,
                Entity.name.label("entity_name"),
                Entity.id.label("entity_id"),
                entity_totals_subq.c.total_followers,
                entity_totals_subq.c.entity_rank,
                PageHistoryRepository._profile_url_case(Page, ph_alias).label("profile_url"),
                PageHistoryRepository._description_case(Page, ph_alias).label("description"),
                page_followers.label("followers"),
            )
            .join(Page, Page.uuid == ph_alias.page_id)
            .join(
                latest_history_subq,
                (latest_history_subq.c.page_id == ph_alias.page_id)
                & (latest_history_subq.c.latest_recorded_at == ph_alias.recorded_at)
            )
            .join(Entity, Entity.id == Page.entity_id)
            .join(entity_totals_subq, entity_totals_subq.c.entity_id == Entity.id)
            .where(Page.entity_id == entity_id)
        )

        rows = db.session.execute(stmt).all()

        if len(rows) < 1:
            return []
        
        result = {
            "entity_name": rows[0].entity_name,
            "entity_id": rows[0].entity_id,
            "total_followers": rows[0].total_followers,
            "rank": rows[0].entity_rank,
            "pages": {}
        }

        for row in rows:
            result["pages"][row.platform] = {
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
    def get_all_entities_ranking():
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
        today = datetime.now().date()
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
                if cache.get("month") == current_month and cache.get("data"):
                    return cache["data"]
            except (json.JSONDecodeError, KeyError):
                pass

        # Recompute and save
        data = PageHistoryRepository.get_all_entities_ranking()
        with open(RANKING_CACHE_FILE, 'w') as f:
            json.dump({"month": current_month, "data": data}, f, cls=_UUIDEncoder)
        return data
