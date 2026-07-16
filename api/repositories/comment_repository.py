# Data-access methods for comment repository.
from api.models.comment_model import Comment, db
from api.utils.logging_utils import instrument_repository_class


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
    def update_label(comment_id: int, label: int, commit: bool = True) -> Comment | None:
        """
        Update the label of a comment.
        
        Args:
            comment_id: Primary key of the comment
            label: Label value (0-4)
            commit: Whether to commit the transaction
            
        Returns:
            Comment | None: The updated comment if found
            
        Raises:
            ValueError: If label is not in range 0-4
        """
        if label not in range(5):
            raise ValueError(f"Label must be between 0 and 4, got {label}")
        
        comment = Comment.query.get(comment_id)
        if comment:
            comment.label = label
            if commit:
                db.session.commit()
        return comment
    
    @staticmethod
    def bulk_update_labels(label_updates: list[dict], commit: bool = True) -> int:
        """
        Bulk update labels for multiple comments.
        
        Args:
            label_updates: List of dicts with 'comment_id' and 'label' keys
            commit: Whether to commit the transaction
            
        Returns:
            int: Number of comments updated
        """
        updated_count = 0
        
        for update in label_updates:
            comment_id = update.get('comment_id')
            label = update.get('label')
            
            if label not in range(5):
                continue  # Skip invalid labels
            
            comment = Comment.query.get(comment_id)
            if comment:
                comment.label = label
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
