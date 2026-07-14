# Data-access methods for scraping post result repository.
from datetime import datetime
from api.models.scraping_post_result_model import ScrapingPostResult, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class ScrapingPostResultRepository:
    """Repository for scraping post result database operations."""

    @staticmethod
    def record(
        page_id: str,
        platform: str,
        post_id: str,
        comments_count: int,
        scraping_session_id: str = None,
        commit: bool = True,
    ) -> ScrapingPostResult:
        """
        Upsert a scraping result for a single post.
        If a result already exists for this (page_id, platform, post_id, session_id)
        composite, it is updated; otherwise a new row is inserted.

        Args:
            page_id: Page UUID
            platform: Platform name
            post_id: Post ID
            comments_count: Number of comments inserted (0 is valid — means scraped with no comments)
            scraping_session_id: Optional session UUID
            commit: Whether to commit the transaction

        Returns:
            ScrapingPostResult: The created or updated instance
        """
        result = ScrapingPostResultRepository.get_by_post_and_session(
            page_id, platform, post_id, scraping_session_id
        )

        if result:
            result.comments_count = comments_count
            result.scraped_at = datetime.utcnow()
        else:
            result = ScrapingPostResult(
                page_id=page_id,
                platform=platform,
                post_id=post_id,
                comments_count=comments_count,
                scraping_session_id=scraping_session_id,
                scraped_at=datetime.utcnow(),
            )
            db.session.add(result)

        if commit:
            db.session.commit()

        return result

    @staticmethod
    def get_by_post_and_session(
        page_id: str,
        platform: str,
        post_id: str,
        scraping_session_id: str = None,
    ) -> ScrapingPostResult | None:
        """
        Fetch a scraping result by the composite key.

        Returns:
            ScrapingPostResult | None
        """
        return ScrapingPostResult.query.filter_by(
            page_id=page_id,
            platform=platform,
            post_id=post_id,
            scraping_session_id=scraping_session_id,
        ).first()

    @staticmethod
    def get_scraped_post_keys_in_range(
        start_dt: datetime,
        end_dt: datetime,
        platform: str = None,
    ) -> set[tuple]:
        """
        Return a set of (page_id, platform, post_id) tuples for posts that
        were scraped (i.e. have a ScrapingPostResult row) within the given
        datetime range.

        Args:
            start_dt: Range start (inclusive)
            end_dt: Range end (exclusive)
            platform: Optional platform filter

        Returns:
            set of (str, str, str) tuples
        """
        query = ScrapingPostResult.query.filter(
            ScrapingPostResult.scraped_at >= start_dt,
            ScrapingPostResult.scraped_at < end_dt,
        )
        if platform:
            query = query.filter_by(platform=platform)

        rows = query.with_entities(
            ScrapingPostResult.page_id,
            ScrapingPostResult.platform,
            ScrapingPostResult.post_id,
        ).all()

        return {(str(r.page_id), r.platform, r.post_id) for r in rows}
