# Data-access methods for comment repository.
from datetime import timedelta
from sqlalchemy import func, nullslast
from api.models.comment_model import Comment, db
from api.models.page_model import Page
from api.models.entity_model import Entity
from api.utils.logging_utils import instrument_repository_class


def _apply_comment_window(query, start_date=None, end_date=None):
    """Restrict a comment query to the [start_date, end_date] window.

    `end_date` is a date; we filter `< end_date + 1 day` so the whole end day is
    included (a plain `<= end_date` would drop everything after that midnight).
    """
    if start_date:
        query = query.filter(Comment.comment_timestamp >= start_date)
    if end_date:
        query = query.filter(Comment.comment_timestamp < end_date + timedelta(days=1))
    return query


@instrument_repository_class
class CommentRepository:
    """Repository for comment database operations."""
    
    @staticmethod
    def create(comment_data: dict, commit: bool = True) -> Comment:
        """
        Insert a single comment.
        
        Args:
            comment_data: Dictionary containing comment fields
            commit: Whether to commit the transaction
            
        Returns:
            Comment: The created comment instance
        """
        comment = Comment(**comment_data)
        db.session.add(comment)
        if commit:
            db.session.commit()
        return comment
    
    @staticmethod
    def bulk_create(comments_data: list[dict], commit: bool = True) -> tuple[int, int]:
        """
        Insert multiple comments in a transaction.
        Skips duplicates based on composite unique constraint.
        
        Args:
            comments_data: List of dictionaries containing comment fields
            commit: Whether to commit the transaction
            
        Returns:
            tuple: (inserted_count, skipped_count)
        """
        inserted_count = 0
        skipped_count = 0
        
        for comment_dict in comments_data:
            # Check if comment already exists
            exists = CommentRepository.exists(
                comment_dict['page_id'],
                comment_dict['platform'],
                comment_dict['post_id'],
                comment_dict['comment_id']
            )
            
            if exists:
                skipped_count += 1
                continue
            
            comment = Comment(**comment_dict)
            db.session.add(comment)
            inserted_count += 1
        
        if commit:
            db.session.commit()
        
        return inserted_count, skipped_count
    
    @staticmethod
    def exists(page_id: str, platform: str, post_id: str, comment_id: str) -> bool:
        """
        Check if a comment already exists by composite key.
        
        Args:
            page_id: Page UUID
            platform: Platform name
            post_id: Post ID
            comment_id: Comment ID
            
        Returns:
            bool: True if comment exists
        """
        return db.session.query(
            db.session.query(Comment)
            .filter_by(
                page_id=page_id,
                platform=platform,
                post_id=post_id,
                comment_id=comment_id
            )
            .exists()
        ).scalar()
    
    @staticmethod
    def get_by_composite_key(page_id: str, platform: str, 
                             post_id: str, comment_id: str) -> Comment | None:
        """
        Fetch a single comment by composite key.
        
        Args:
            page_id: Page UUID
            platform: Platform name
            post_id: Post ID
            comment_id: Comment ID
            
        Returns:
            Comment | None: The comment if found
        """
        return Comment.query.filter_by(
            page_id=page_id,
            platform=platform,
            post_id=post_id,
            comment_id=comment_id
        ).first()
    
    @staticmethod
    def get_by_post(page_id: str, platform: str, post_id: str) -> list[Comment]:
        """
        Get all comments for a specific post.
        
        Args:
            page_id: Page UUID
            platform: Platform name
            post_id: Post ID
            
        Returns:
            list[Comment]: List of comments
        """
        return Comment.query.filter_by(
            page_id=page_id,
            platform=platform,
            post_id=post_id
        ).order_by(Comment.comment_timestamp.desc()).all()
    
    @staticmethod
    def get_by_session(session_id: str) -> list[Comment]:
        """
        Get all comments inserted during a specific scraping session.
        
        Args:
            session_id: Session UUID
            
        Returns:
            list[Comment]: List of comments
        """
        return Comment.query.filter_by(
            scraping_session_id=session_id
        ).order_by(Comment.recorded_at.desc()).all()
    
    @staticmethod
    def count_by_post(page_id: str, platform: str, post_id: str) -> int:
        """
        Count comments for a specific post.
        
        Args:
            page_id: Page UUID
            platform: Platform name
            post_id: Post ID
            
        Returns:
            int: Number of comments
        """
        return Comment.query.filter_by(
            page_id=page_id,
            platform=platform,
            post_id=post_id
        ).count()
    
    @staticmethod
    def update_label(comment_id: int, label: int, confidence: float | None = None, 
                     commit: bool = True) -> Comment | None:
        """
        Update the label (and optionally confidence) of a comment.
        
        Args:
            comment_id: Primary key of the comment
            label: Label value (0-4)
            confidence: Confidence score (0.0 to 1.0), optional
            commit: Whether to commit the transaction
            
        Returns:
            Comment | None: The updated comment if found
            
        Raises:
            ValueError: If label is not in range 0-4 or confidence is out of range
        """
        if label not in range(5):
            raise ValueError(f"Label must be between 0 and 4, got {label}")
        
        if confidence is not None and not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")
        
        comment = Comment.query.get(comment_id)
        if comment:
            comment.label = label
            if confidence is not None:
                comment.confidence = confidence
            if commit:
                db.session.commit()
        return comment
    
    @staticmethod
    def bulk_update_labels(label_updates: list[dict], commit: bool = True) -> int:
        """
        Bulk update labels and confidence scores for multiple comments.
        Also marks comments as processed.
        
        Args:
            label_updates: List of dicts with 'comment_id', 'label', and optional 'confidence' keys
            commit: Whether to commit the transaction
            
        Returns:
            int: Number of comments updated
        """
        updated_count = 0
        
        for update in label_updates:
            comment_id = update.get('comment_id')
            label = update.get('label')
            confidence = update.get('confidence')
            
            if label not in range(5):
                continue  # Skip invalid labels
            
            if confidence is not None and not (0.0 <= confidence <= 1.0):
                continue  # Skip invalid confidence scores
            
            comment = Comment.query.get(comment_id)
            if comment:
                comment.label = label
                if confidence is not None:
                    comment.confidence = confidence
                comment.is_processed = True
                updated_count += 1
        
        if commit:
            db.session.commit()
        
        return updated_count
    
    @staticmethod
    def get_unlabeled(limit: int | None = None) -> list[Comment]:
        """
        Get comments that have not been labeled yet.
        
        Args:
            limit: Maximum number of comments to return (optional)
            
        Returns:
            list[Comment]: List of unlabeled comments
        """
        query = Comment.query.filter_by(label=None).order_by(Comment.recorded_at.desc())
        if limit:
            query = query.limit(limit)
        return query.all()
    
    @staticmethod
    def get_unprocessed(limit: int | None = None) -> list[Comment]:
        """
        Get comments that have not been processed yet.
        
        Args:
            limit: Maximum number of comments to return (optional)
            
        Returns:
            list[Comment]: List of unprocessed comments
        """
        query = Comment.query.filter_by(is_processed=False).order_by(Comment.recorded_at.desc())
        if limit:
            query = query.limit(limit)
        return query.all()
    
    @staticmethod
    def get_by_label(label: int) -> list[Comment]:
        """
        Get all comments with a specific label.
        
        Args:
            label: Label value (0-4)
            
        Returns:
            list[Comment]: List of comments with the specified label
            
        Raises:
            ValueError: If label is not in range 0-4
        """
        if label not in range(5):
            raise ValueError(f"Label must be between 0 and 4, got {label}")
        
        return Comment.query.filter_by(label=label).order_by(Comment.recorded_at.desc()).all()
    
    @staticmethod
    def mark_processed(comment_id: int, commit: bool = True) -> Comment | None:
        """
        Mark a comment as processed.
        
        Args:
            comment_id: Primary key of the comment
            commit: Whether to commit the transaction
            
        Returns:
            Comment | None: The updated comment if found
        """
        comment = Comment.query.get(comment_id)
        if comment:
            comment.is_processed = True
            if commit:
                db.session.commit()
        return comment
    
    @staticmethod
    def bulk_mark_processed(comment_ids: list[int], commit: bool = True) -> int:
        """
        Mark multiple comments as processed.
        
        Args:
            comment_ids: List of comment primary keys
            commit: Whether to commit the transaction
            
        Returns:
            int: Number of comments updated
        """
        updated_count = Comment.query.filter(Comment.id.in_(comment_ids)).update(
            {Comment.is_processed: True}, synchronize_session=False
        )
        
        if commit:
            db.session.commit()
        
        return updated_count
    
    @staticmethod
    def count_unprocessed() -> int:
        """
        Count comments that have not been processed yet.
        
        Returns:
            int: Number of unprocessed comments
        """
        return Comment.query.filter_by(is_processed=False).count()
    
    @staticmethod
    def count_by_processing_status(is_processed: bool) -> int:
        """
        Count comments by processing status.

        Args:
            is_processed: Processing status to filter by

        Returns:
            int: Number of comments matching the status
        """
        return Comment.query.filter_by(is_processed=is_processed).count()

    # ── Sentiment aggregation ─────────────────────────────────────────────
    # Sentiment is stored per comment as `label` (int 0-4) + `confidence`.
    # A comment links to a brand via page_id -> pages.uuid -> pages.entity_id.
    # All aggregations ignore unlabeled comments (label IS NULL).

    @staticmethod
    def get_sentiment_counts_by_entity(
        entity_id: int, start_date=None, end_date=None
    ) -> list[tuple]:
        """
        Count labeled comments per sentiment label for one entity/brand.

        Args:
            entity_id: The entity (brand) id
            start_date: Optional lower bound on comment_timestamp
            end_date: Optional (inclusive) upper bound on comment_timestamp

        Returns:
            list[tuple]: rows of (label, count, avg_confidence)
        """
        q = (
            db.session.query(
                Comment.label,
                func.count(Comment.id),
                func.avg(Comment.confidence),
            )
            .join(Page, Page.uuid == Comment.page_id)
            .filter(Page.entity_id == entity_id, Comment.label.isnot(None))
        )
        q = _apply_comment_window(q, start_date, end_date)
        return q.group_by(Comment.label).order_by(Comment.label).all()

    @staticmethod
    def get_sentiment_trend_by_entity(
        entity_id: int, start_date=None, end_date=None
    ) -> list[tuple]:
        """
        Count labeled comments per (day, label) for one entity, for a trend chart.

        Returns:
            list[tuple]: rows of (day, label, count), ordered by day
        """
        day = func.date(Comment.comment_timestamp)
        q = (
            db.session.query(day, Comment.label, func.count(Comment.id))
            .join(Page, Page.uuid == Comment.page_id)
            .filter(Page.entity_id == entity_id, Comment.label.isnot(None))
        )
        q = _apply_comment_window(q, start_date, end_date)
        return q.group_by(day, Comment.label).order_by(day).all()

    @staticmethod
    def get_example_comments_by_entity(
        entity_id: int, label: int, limit: int = 5, start_date=None, end_date=None
    ) -> list[Comment]:
        """
        Highest-confidence example comments with a given label for one entity,
        within the same [start_date, end_date] window as the aggregates.

        Returns:
            list[Comment]: up to `limit` comments, most confident first
        """
        q = (
            db.session.query(Comment)
            .join(Page, Page.uuid == Comment.page_id)
            .filter(Page.entity_id == entity_id, Comment.label == label)
        )
        q = _apply_comment_window(q, start_date, end_date)
        return q.order_by(nullslast(Comment.confidence.desc())).limit(limit).all()

    @staticmethod
    def get_sentiment_counts_by_post(
        page_id: str, platform: str, post_id: str
    ) -> list[tuple]:
        """
        Count labeled comments per sentiment label for one post.

        Returns:
            list[tuple]: rows of (label, count, avg_confidence)
        """
        return (
            db.session.query(
                Comment.label,
                func.count(Comment.id),
                func.avg(Comment.confidence),
            )
            .filter(
                Comment.page_id == page_id,
                Comment.platform == platform,
                Comment.post_id == post_id,
                Comment.label.isnot(None),
            )
            .group_by(Comment.label)
            .order_by(Comment.label)
            .all()
        )

    @staticmethod
    def get_example_comments_by_post(
        page_id: str, platform: str, post_id: str, label: int, limit: int = 5
    ) -> list[Comment]:
        """
        Highest-confidence example comments with a given label for one post.

        Returns:
            list[Comment]: up to `limit` comments, most confident first
        """
        return (
            Comment.query.filter(
                Comment.page_id == page_id,
                Comment.platform == platform,
                Comment.post_id == post_id,
                Comment.label == label,
            )
            .order_by(nullslast(Comment.confidence.desc()))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_sentiment_ranking(start_date=None, end_date=None) -> list[tuple]:
        """
        Count labeled comments per (entity, label) across all entities.

        Args:
            start_date: Optional lower bound on comment_timestamp
            end_date: Optional (inclusive) upper bound on comment_timestamp

        Returns:
            list[tuple]: rows of (entity_id, entity_name, entity_type, label, count)
        """
        q = (
            db.session.query(
                Entity.id,
                Entity.name,
                Entity.type,
                Comment.label,
                func.count(Comment.id),
            )
            .join(Page, Page.uuid == Comment.page_id)
            .join(Entity, Entity.id == Page.entity_id)
            .filter(Comment.label.isnot(None))
        )
        q = _apply_comment_window(q, start_date, end_date)
        return q.group_by(
            Entity.id, Entity.name, Entity.type, Comment.label
        ).all()
