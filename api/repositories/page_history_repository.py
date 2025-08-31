from api import db
from api.models import PageHistory
from api.models.category_model import Category
from api.models.entity_category_model import EntityCategory
from api.models.entity_model import Entity
from api.models.page_model import Page
from sqlalchemy import case, select, and_, cast, text
from sqlalchemy.orm import aliased
from sqlalchemy.dialects.postgresql import JSONB


from datetime import date, datetime, time

class PageHistoryRepository:
    @staticmethod
    def get_by_id(history_id: int) -> PageHistory | None:
        return PageHistory.query.get(history_id)

    @staticmethod
    def get_all() -> list[PageHistory]:
        return PageHistory.query.all()

    @staticmethod
    def get_today_all() -> list[PageHistory]:
        today = date.today()
        return db.session.scalars(
            select(PageHistory).where(db.func.date(PageHistory.recorded_at) == today)
        ).all()
    
    @staticmethod
    def get_followers_history_by_entity(entity_id: int):
        stmt = (
            select(
                PageHistory.recorded_at,
                PageHistory.data['followers'].astext.cast(db.Integer).label("followers"),
                PageHistory.page_id,
                Page.platform
            )
            .join(Page, PageHistory.page_id == Page.uuid)
            .where(Page.entity_id == entity_id)
            .order_by(PageHistory.recorded_at)
        )
        return db.session.execute(stmt).all()
    
    @staticmethod
    def get_entity_recent_posts(entity_id: int):
        stmt = (
            select(
                Page.uuid.label("page_id"),
                Page.name.label("page_name"),
                Page.platform,
                case(
                    (Page.platform == "instagram", db.func.coalesce(db.func.jsonb_path_query_array(PageHistory.data, '$.posts[0 to 4]'), cast(text("'[]'"), JSONB))),
                    (Page.platform == "linkedin", db.func.coalesce(db.func.jsonb_path_query_array(PageHistory.data, '$.updates[0 to 4]'), cast(text("'[]'"), JSONB))),
                    (Page.platform == "tiktok", db.func.coalesce(db.func.jsonb_path_query_array(PageHistory.data, '$.top_posts_data[0 to 4]'), cast(text("'[]'"), JSONB))),
                    (Page.platform == "youtube", db.func.coalesce(db.func.jsonb_path_query_array(PageHistory.data, '$.top_videos[0 to 4]'), cast(text("'[]'"), JSONB))),
                    else_=None
                ).label("posts")
            )
            .select_from(PageHistory)
            .join(Page, PageHistory.page_id == Page.uuid)
            .where(Page.entity_id == entity_id)
        )

        rows = db.session.execute(stmt).all()
        return [
            {
                "page_id": row.page_id,
                "page_name": row.page_name,
                "platform": row.platform,
                "posts": row.posts
            }
            for row in rows
        ]
    
    @staticmethod
    def get_entity_info_from_history(entity_id: int):
        # Step 1: Get latest history per page
        latest_history_subq = (
            select(
                PageHistory.page_id,
                db.func.max(PageHistory.recorded_at).label("latest_recorded_at")
            )
            .group_by(PageHistory.page_id)
            .subquery()
        )

        ph_alias = aliased(PageHistory)

        # Step 2: Followers per page (handle youtube vs others)
        page_followers = case(
            (Page.platform == "youtube", ph_alias.data["subscribers"]),
            else_=ph_alias.data["followers"]
        ).cast(db.Integer)

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
                case(
                    (Page.platform == "youtube", ph_alias.data["profile_image"]),
                    (Page.platform == "x", ph_alias.data["profile_image_link"]),
                    (Page.platform == "tiktok", ph_alias.data["profile_pic_url"]),
                    (Page.platform == "linkedin", ph_alias.data["logo"]),
                    (Page.platform == "instagram", ph_alias.data["profile_image_link"]),
                ).label("profile_url"),
                case(
                    (Page.platform == "youtube", ph_alias.data["Description"]),
                    (Page.platform == "x", ph_alias.data["biography"]),
                    (Page.platform == "tiktok", ph_alias.data["biography"]),
                    (Page.platform == "linkedin", ph_alias.data["about"]),
                    (Page.platform == "instagram", ph_alias.data["biography"]),
                ).label("description"),
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
    def get_all_entities_ranking():
        # --- Step 1: Subquery to get latest history per page ---
# --- Step 1: Latest snapshot per page (instead of separate latest_history_subq + ph join) ---
        latest_page_data = (
            select(
                PageHistory.page_id,
                PageHistory.recorded_at,
                case(
                    (Page.platform == "youtube", PageHistory.data["subscribers"]),
                    else_=PageHistory.data["followers"]
                ).cast(db.Integer).label("followers"),
                case(
                    (Page.platform == "youtube", PageHistory.data["profile_image"]),
                    (Page.platform == "x", PageHistory.data["profile_image_link"]),
                    (Page.platform == "tiktok", PageHistory.data["profile_pic_url"]),
                    (Page.platform == "linkedin", PageHistory.data["logo"]),
                    (Page.platform == "instagram", PageHistory.data["profile_image_link"]),
                ).label("profile_url")
            )
            .join(Page, Page.uuid == PageHistory.page_id)
            .where(
                PageHistory.recorded_at
                == select(db.func.max(PageHistory.recorded_at))
                .where(PageHistory.page_id == Page.uuid)
                .correlate(Page)
                .scalar_subquery()
            )
            .subquery()
        )

        # --- Step 2: Aggregate per entity ---
        entity_totals = (
            select(
                Entity.id.label("entity_id"),
                Category.name.label("category_name"),
                db.func.sum(latest_page_data.c.followers).label("total_followers"),
                db.func.rank()
                    .over(order_by=db.func.sum(latest_page_data.c.followers).desc())
                    .label("entity_rank"),
            )
            .join(Page, Page.entity_id == Entity.id)
            .join(latest_page_data, latest_page_data.c.page_id == Page.uuid)
            .join(EntityCategory, EntityCategory.entity_id == Entity.id)
            .join(Category, Category.id == EntityCategory.category_id)
            .group_by(Entity.id, Category.name)
            .subquery()
        )

        # --- Step 3: Final query (no second join to PageHistory needed) ---
        stmt = (
            select(
                Entity.id.label("entity_id"),
                Entity.name.label("entity_name"),
                entity_totals.c.total_followers,
                entity_totals.c.entity_rank,
                entity_totals.c.category_name,
                Page.platform,
                Page.uuid.label("page_id"),
                Page.link.label("page_url"),
                latest_page_data.c.profile_url,
                latest_page_data.c.followers,
            )
            .join(Page, Page.entity_id == Entity.id)
            .join(latest_page_data, latest_page_data.c.page_id == Page.uuid)
            .join(entity_totals, entity_totals.c.entity_id == Entity.id)
            .order_by(entity_totals.c.entity_rank)
        )

        rows = db.session.execute(stmt).all()
        if len(rows) < 1:
            return []
        # --- Step 4: Build result dict ---
        result = {}
        for row in rows:
            if row.entity_id not in result:
                result[row.entity_id] = {
                    "entity_id": row.entity_id,
                    "entity_name": row.entity_name,
                    "total_followers": row.total_followers,
                    "rank": row.entity_rank,
                    "category": row.category_name,
                    "platforms": {}
                }

            result[row.entity_id]["platforms"][row.platform] = {
                "page_id": row.page_id,
                "followers": row.followers,
                "profile_url": row.profile_url,
                "page_url": row.page_url,
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
    def get_platform_history(self, platform: str):
        stmt =( select(PageHistory)
            .join(Page, PageHistory.page_id == Page.uuid)
            .filter(Page.platform == platform)
        )
            
        return db.session.scalars(stmt).all()
    


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
