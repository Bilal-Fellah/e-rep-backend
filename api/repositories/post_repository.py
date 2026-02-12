from sqlalchemy.dialects.postgresql import insert
from datetime import datetime
from api.models.entity_model import Entity
from api.models.post_model import db, Post, PostHistory


class PostRepository:
    @staticmethod
    def get_by_id(post_id: int) -> Post | None:
        return Post.query.get(post_id)

    @staticmethod
    def upsert_post(page_id, platform, post_id, created_at, url=None,
                    likes=None, comments=None, shares=None, views=None,
                    caption=None, content_type=None, image_url=None, video_url=None,
                    is_pinned=None, extra_data=None):
        """
        Insert a new post or update if it exists.
        Returns the Post instance.
        """
        stmt = insert(Post).values(
            page_id=page_id,
            platform=platform,
            post_id=post_id,
            created_at=created_at,
            url=url,
            likes=likes,
            comments=comments,
            shares=shares,
            views=views,
            caption=caption,
            content_type=content_type,
            image_url=image_url,
            video_url=video_url,
            is_pinned=is_pinned,
            extra_data=extra_data
        ).on_conflict_do_update(
            constraint="uix_post_platform_page",
            set_={
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "views": views,
                "url": url,
                "caption": caption,
                "content_type": content_type,
                "image_url": image_url,
                "video_url": video_url,
                "is_pinned": is_pinned,
                "extra_data": extra_data
            }
        ).returning(Post.id)
        
        result = db.session.execute(stmt)
        db.session.commit()
        post_id_db = result.scalar()  # get the inserted/updated post id
        return Post.query.get(post_id_db)

    @staticmethod
    def add_history(post: Post):
        """
        Add a snapshot of the post to PostHistory.
        """
        snapshot = PostHistory(
            post_id=post.id,
            recorded_at=datetime.utcnow(),
            likes=post.likes,
            comments=post.comments,
            shares=post.shares,
            views=post.views,
            extra_data=post.extra_data
        )
        db.session.add(snapshot)
        db.session.commit()
        return snapshot

    @staticmethod
    def get_post_by_platform(platform):
        return Post.query.filter_by(
            platform=platform
        ).all()

    @staticmethod
    def get_posts_by_page(page_id, platform=None):
        query = Post.query.filter_by(page_id=page_id)
        if platform:
            query = query.filter_by(platform=platform)
        return query.all()

    @staticmethod
    def get_post_history(post_id):
        return PostHistory.query.filter_by(post_id=post_id).order_by(PostHistory.recorded_at.desc()).all()
