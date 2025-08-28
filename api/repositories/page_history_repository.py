from api import db
from api.models import PageHistory
from api.models.entity_model import Entity
from api.models.page_model import Page
from sqlalchemy import case, select, and_
from sqlalchemy.orm import aliased

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
                    (Page.platform == "instagram", db.func.jsonb_path_query_array(PageHistory.data, '$.posts[0 to 4]')),
                    (Page.platform == "linkedin", db.func.jsonb_path_query_array(PageHistory.data, '$.updates[0 to 4]')),
                    (Page.platform == "tiktok", db.func.jsonb_path_query_array(PageHistory.data, '$.top_posts_data[0 to 4]')),
                    (Page.platform == "youtube", db.func.jsonb_path_query_array(PageHistory.data, '$.top_videos[0 to 4]')),
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
        latest_history_subq = (
            select(
                PageHistory.page_id,
                db.func.max(PageHistory.recorded_at).label("latest_recorded_at")
            )
            .group_by(PageHistory.page_id)
            .subquery()
        )

        ph_alias = aliased(PageHistory)

        # Followers column (subscribers for YT, followers otherwise)
        page_followers = case(
            (Page.platform == "youtube", ph_alias.data["subscribers"]),
            else_=ph_alias.data["followers"]
        ).cast(db.Integer)

        # --- Step 2: Aggregate per entity (total followers + rank) ---
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

        # --- Step 3: Query pages + join entity totals ---
        stmt = (
            select(
                Entity.id.label("entity_id"),
                Entity.name.label("entity_name"),
                entity_totals_subq.c.total_followers,
                entity_totals_subq.c.entity_rank,
                Page.platform,
                Page.uuid.label("page_id"),
                Page.link.label("page_url"),
                case(
                    (Page.platform == "youtube", ph_alias.data["profile_image"]),
                    (Page.platform == "x", ph_alias.data["profile_image_link"]),
                    (Page.platform == "tiktok", ph_alias.data["profile_pic_url"]),
                    (Page.platform == "linkedin", ph_alias.data["logo"]),
                    (Page.platform == "instagram", ph_alias.data["profile_image_link"]),
                ).label("profile_url"),
                
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
            .order_by(entity_totals_subq.c.entity_rank)
        )

        rows = db.session.execute(stmt).all()

        # --- Step 4: Build result dict ---
        result = {}
        for row in rows:
            if row.entity_id not in result:
                result[row.entity_id] = {
                    "entity_id": row.entity_id,
                    "entity_name": row.entity_name,
                    "total_followers": row.total_followers,
                    "rank": row.entity_rank,
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
    # @staticmethod
    # def get_latest_history_for_page(page_id):
    #     """Return the most recent PageHistory row for a page."""
    #     stmt = (
    #         select(PageHistory)
    #         .where(PageHistory.page_id == page_id)
    #         .order_by(PageHistory.recorded_at.desc())
    #         .limit(1)
    #     )
    #     return db.session.scalar(stmt)

    # @staticmethod
    # def extract_profile_url(page, history):
    #     """Choose correct image field depending on platform."""
    #     platform = page.platform
    #     data = history.data

    #     mapping = {
    #         "youtube": data.get("profile_image"),
    #         "x": data.get("profile_image_link"),
    #         "tiktok": data.get("profile_pic_url"),
    #         "linkedin": data.get("logo"),
    #         "instagram": data.get("profile_image_link"),
    #     }
    #     return mapping.get(platform)

    # @staticmethod
    # def extract_followers(page, history):
    #     """Choose correct followers/subscribers field."""
    #     data = history.data
    #     if page.platform == "youtube":
    #         return data.get("subscribers")
    #     return data.get("followers")

    # @staticmethod
    # def get_entity_info(entity_id):
    #     """Main entry point: build structured data with score and rank."""
    #     stmt = select(Page).where(Page.entity_id == entity_id)
    #     pages = db.session.scalars(stmt).all()

    #     result = {}
    #     for page in pages:
    #         history = PageHistoryRepository.get_latest_history_for_page(page.uuid)
    #         if not history:
    #             continue

    #         image_url = PageHistoryRepository.extract_profile_url(page, history)
    #         followers = PageHistoryRepository.extract_followers(page, history)

    #         result[page.platform] = {
    #             "page_id": page.uuid,
    #             "image_url": image_url,
    #             "followers": followers,
    #             "score": PageHistoryRepository.compute_score(page, followers),
    #             "rank": PageHistoryRepository.compute_rank(page, followers),
    #         }

    #     return result

    # @staticmethod
    # def compute_score(page, followers):
    #     """Placeholder: implement real scoring logic here."""
    #     if not followers:
    #         return 0
    #     return int(followers) // 1000  # example: 1 point per 1k followers

    # @staticmethod
    # def compute_rank(entity_id):
    #     rank_all = (
    #         select (
    #             Entity.id,
    #             db.func.rank().over(order_by=db.func.sum())
    #         )
    #     )
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
