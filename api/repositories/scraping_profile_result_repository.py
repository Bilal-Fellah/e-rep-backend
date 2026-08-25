# Data-access methods for scraping profile result repository. Mirrors
# scraping_post_result_repository.py.
from datetime import datetime
from api.models.scraping_profile_result_model import ScrapingProfileResult, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class ScrapingProfileResultRepository:
    @staticmethod
    def record(
        page_id: str,
        platform: str,
        account_id: str,
        profile_inserted: bool,
        scraping_session_id: str = None,
        commit: bool = True,
    ) -> ScrapingProfileResult:
        """Upsert a scraping result for a single account. If a result
        already exists for this (page_id, platform, session) composite, it
        is updated; otherwise a new row is inserted."""
        result = ScrapingProfileResultRepository.get_by_page_and_session(
            page_id, platform, scraping_session_id
        )

        if result:
            result.account_id = account_id
            result.profile_inserted = profile_inserted
            result.scraped_at = datetime.utcnow()
        else:
            result = ScrapingProfileResult(
                page_id=page_id,
                platform=platform,
                account_id=account_id,
                profile_inserted=profile_inserted,
                scraping_session_id=scraping_session_id,
                scraped_at=datetime.utcnow(),
            )
            db.session.add(result)

        if commit:
            db.session.commit()
        else:
            db.session.flush()

        return result

    @staticmethod
    def get_by_page_and_session(
        page_id: str,
        platform: str,
        scraping_session_id: str = None,
    ) -> ScrapingProfileResult | None:
        return ScrapingProfileResult.query.filter_by(
            page_id=page_id,
            platform=platform,
            scraping_session_id=scraping_session_id,
        ).first()

    @staticmethod
    def get_scraped_page_ids_in_range(
        start_dt: datetime,
        end_dt: datetime,
        platform: str = None,
    ) -> set[str]:
        """page_ids with a ScrapingProfileResult row (visited, whether or
        not it yielded data) within the given datetime range — used to
        exclude accounts already handled today from the next fetch."""
        query = ScrapingProfileResult.query.filter(
            ScrapingProfileResult.scraped_at >= start_dt,
            ScrapingProfileResult.scraped_at < end_dt,
        )
        if platform:
            query = query.filter_by(platform=platform)

        rows = query.with_entities(ScrapingProfileResult.page_id).all()
        return {str(r.page_id) for r in rows}
