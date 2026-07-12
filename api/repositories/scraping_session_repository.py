# Data-access methods for scraping session repository.
from datetime import datetime
from api.models.scraping_session_model import ScrapingSession, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class ScrapingSessionRepository:
    """Repository for scraping session database operations."""
    
    @staticmethod
    def create(posts_fetched: int, commit: bool = True) -> ScrapingSession:
        """
        Create a new scraping session with initial post count.
        
        Args:
            posts_fetched: Number of posts fetched
            commit: Whether to commit the transaction
            
        Returns:
            ScrapingSession: The created session instance
        """
        session = ScrapingSession(posts_fetched=posts_fetched)
        db.session.add(session)
        if commit:
            db.session.commit()
        return session
    
    @staticmethod
    def get_by_id(session_id: str) -> ScrapingSession | None:
        """
        Fetch a session by ID.
        
        Args:
            session_id: Session UUID
            
        Returns:
            ScrapingSession | None: The session if found
        """
        return ScrapingSession.query.filter_by(session_id=session_id).first()
    
    @staticmethod
    def update_status(session_id: str, status: str, 
                     error_message: str = None, commit: bool = True) -> ScrapingSession:
        """
        Update session status and optional error message.
        
        Args:
            session_id: Session UUID
            status: New status (pending, completed, failed)
            error_message: Optional error message
            commit: Whether to commit the transaction
            
        Returns:
            ScrapingSession: The updated session
        """
        session = ScrapingSessionRepository.get_by_id(session_id)
        if session:
            session.status = status
            if error_message:
                session.error_message = error_message
            if commit:
                db.session.commit()
        return session
    
    @staticmethod
    def increment_comments(session_id: str, count: int, commit: bool = True) -> ScrapingSession:
        """
        Increment the comments_inserted counter.
        
        Args:
            session_id: Session UUID
            count: Number to increment by
            commit: Whether to commit the transaction
            
        Returns:
            ScrapingSession: The updated session
        """
        session = ScrapingSessionRepository.get_by_id(session_id)
        if session:
            session.comments_inserted += count
            if commit:
                db.session.commit()
        return session
    
    @staticmethod
    def complete_session(session_id: str, commit: bool = True) -> ScrapingSession:
        """
        Mark session as completed with timestamp.
        
        Args:
            session_id: Session UUID
            commit: Whether to commit the transaction
            
        Returns:
            ScrapingSession: The updated session
        """
        session = ScrapingSessionRepository.get_by_id(session_id)
        if session:
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            if commit:
                db.session.commit()
        return session
    
    @staticmethod
    def get_all(limit: int = 100, offset: int = 0) -> list[ScrapingSession]:
        """
        Get all sessions with pagination.
        
        Args:
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            
        Returns:
            list[ScrapingSession]: List of sessions
        """
        return (ScrapingSession.query
                .order_by(ScrapingSession.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all())
