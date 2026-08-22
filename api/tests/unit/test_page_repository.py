"""
Unit tests for PageRepository.get_pages_by_ids() method.
Tests filtering by UUIDs, active entities, and platform.
"""
import pytest
from uuid import uuid4
from api.repositories.page_repository import PageRepository
from api.models import Page, Entity
from api import db


class TestGetPagesByIds:
    """Test suite for get_pages_by_ids() method."""

    def test_returns_empty_list_when_no_page_ids_provided(self, app):
        """Should return empty list when page_ids is empty."""
        with app.app_context():
            result = PageRepository.get_pages_by_ids([])
            assert isinstance(result, list)
            assert len(result) == 0

    def test_returns_empty_list_when_no_matching_pages(self, app):
        """Should return empty list when no pages match the provided UUIDs."""
        with app.app_context():
            # Use random UUIDs that don't exist in database
            random_uuids = [uuid4(), uuid4()]
            result = PageRepository.get_pages_by_ids(random_uuids)
            assert len(result) == 0

    def test_returns_pages_matching_provided_ids(self, app):
        """Should return pages that match the provided UUIDs."""
        with app.app_context():
            # Create entity and pages
            entity = Entity(name="Test Brand", type="company", to_scrape=True)
            db.session.add(entity)
            db.session.flush()
            
            page1 = Page(
                uuid=uuid4(),
                name="instagram_page",
                link="https://instagram.com/testbrand",
                platform="instagram",
                entity_id=entity.id
            )
            page2 = Page(
                uuid=uuid4(),
                name="facebook_page",
                link="https://facebook.com/testbrand",
                platform="facebook",
                entity_id=entity.id
            )
            db.session.add_all([page1, page2])
            db.session.commit()
            
            # Query by page IDs
            result = PageRepository.get_pages_by_ids([page1.uuid, page2.uuid])
            
            assert len(result) == 2
            returned_uuids = [page.uuid for page in result]
            assert page1.uuid in returned_uuids
            assert page2.uuid in returned_uuids
            
            # Cleanup
            db.session.delete(page1)
            db.session.delete(page2)
            db.session.delete(entity)
            db.session.commit()

    def test_filters_by_active_entities_only(self, app):
        """Should only return pages belonging to active entities (to_scrape=True)."""
        with app.app_context():
            # Create active entity
            active_entity = Entity(name="Active Brand", type="company", to_scrape=True)
            db.session.add(active_entity)
            db.session.flush()
            
            # Create inactive entity
            inactive_entity = Entity(name="Inactive Brand", type="company", to_scrape=False)
            db.session.add(inactive_entity)
            db.session.flush()
            
            # Create pages for both entities
            active_page = Page(
                uuid=uuid4(),
                name="active_page",
                link="https://instagram.com/activebrand",
                platform="instagram",
                entity_id=active_entity.id
            )
            inactive_page = Page(
                uuid=uuid4(),
                name="inactive_page",
                link="https://instagram.com/inactivebrand",
                platform="instagram",
                entity_id=inactive_entity.id
            )
            db.session.add_all([active_page, inactive_page])
            db.session.commit()
            
            # Query for both page IDs
            result = PageRepository.get_pages_by_ids([active_page.uuid, inactive_page.uuid])
            
            # Should only return active page
            assert len(result) == 1
            assert result[0].uuid == active_page.uuid
            assert result[0].entity.to_scrape is True
            
            # Cleanup
            db.session.delete(active_page)
            db.session.delete(inactive_page)
            db.session.delete(active_entity)
            db.session.delete(inactive_entity)
            db.session.commit()

    def test_filters_by_platform_when_provided(self, app):
        """Should filter by platform when platform parameter is provided."""
        with app.app_context():
            # Create entity
            entity = Entity(name="Multi Platform Brand", type="company", to_scrape=True)
            db.session.add(entity)
            db.session.flush()
            
            # Create pages on different platforms
            instagram_page = Page(
                uuid=uuid4(),
                name="instagram_page",
                link="https://instagram.com/multiplatform",
                platform="instagram",
                entity_id=entity.id
            )
            facebook_page = Page(
                uuid=uuid4(),
                name="facebook_page",
                link="https://facebook.com/multiplatform",
                platform="facebook",
                entity_id=entity.id
            )
            tiktok_page = Page(
                uuid=uuid4(),
                name="tiktok_page",
                link="https://tiktok.com/@multiplatform",
                platform="tiktok",
                entity_id=entity.id
            )
            db.session.add_all([instagram_page, facebook_page, tiktok_page])
            db.session.commit()
            
            # Query with platform filter
            result = PageRepository.get_pages_by_ids(
                [instagram_page.uuid, facebook_page.uuid, tiktok_page.uuid],
                platform="instagram"
            )
            
            # Should only return Instagram page
            assert len(result) == 1
            assert result[0].uuid == instagram_page.uuid
            assert result[0].platform == "instagram"
            
            # Cleanup
            db.session.delete(instagram_page)
            db.session.delete(facebook_page)
            db.session.delete(tiktok_page)
            db.session.delete(entity)
            db.session.commit()

    def test_returns_all_platforms_when_platform_not_provided(self, app):
        """Should return pages from all platforms when platform filter is not provided."""
        with app.app_context():
            # Create entity
            entity = Entity(name="Multi Platform Brand", type="company", to_scrape=True)
            db.session.add(entity)
            db.session.flush()
            
            # Create pages on different platforms
            instagram_page = Page(
                uuid=uuid4(),
                name="instagram_page",
                link="https://instagram.com/allplatforms",
                platform="instagram",
                entity_id=entity.id
            )
            facebook_page = Page(
                uuid=uuid4(),
                name="facebook_page",
                link="https://facebook.com/allplatforms",
                platform="facebook",
                entity_id=entity.id
            )
            db.session.add_all([instagram_page, facebook_page])
            db.session.commit()
            
            # Query without platform filter
            result = PageRepository.get_pages_by_ids([instagram_page.uuid, facebook_page.uuid])
            
            # Should return both pages
            assert len(result) == 2
            platforms = [page.platform for page in result]
            assert "instagram" in platforms
            assert "facebook" in platforms
            
            # Cleanup
            db.session.delete(instagram_page)
            db.session.delete(facebook_page)
            db.session.delete(entity)
            db.session.commit()

    def test_loads_entity_relationship(self, app):
        """Should load entity relationship for returned pages."""
        with app.app_context():
            # Create entity with specific name
            entity = Entity(name="Brand With Relationship", type="company", to_scrape=True)
            db.session.add(entity)
            db.session.flush()
            
            # Create page
            page = Page(
                uuid=uuid4(),
                name="test_page",
                link="https://instagram.com/relationshiptest",
                platform="instagram",
                entity_id=entity.id
            )
            db.session.add(page)
            db.session.commit()
            
            # Query page
            result = PageRepository.get_pages_by_ids([page.uuid])
            
            # Verify entity relationship is loaded
            assert len(result) == 1
            assert result[0].entity is not None
            assert result[0].entity.name == "Brand With Relationship"
            assert result[0].entity.to_scrape is True
            
            # Cleanup
            db.session.delete(page)
            db.session.delete(entity)
            db.session.commit()

    def test_handles_partial_matches(self, app):
        """Should return only matching pages when some UUIDs don't exist."""
        with app.app_context():
            # Create entity and one page
            entity = Entity(name="Partial Match Brand", type="company", to_scrape=True)
            db.session.add(entity)
            db.session.flush()
            
            existing_page = Page(
                uuid=uuid4(),
                name="existing_page",
                link="https://instagram.com/existing",
                platform="instagram",
                entity_id=entity.id
            )
            db.session.add(existing_page)
            db.session.commit()
            
            # Query with one existing and one non-existing UUID
            non_existing_uuid = uuid4()
            result = PageRepository.get_pages_by_ids([existing_page.uuid, non_existing_uuid])
            
            # Should only return the existing page
            assert len(result) == 1
            assert result[0].uuid == existing_page.uuid
            
            # Cleanup
            db.session.delete(existing_page)
            db.session.delete(entity)
            db.session.commit()

    def test_combined_filters_active_entity_and_platform(self, app):
        """Should apply both active entity and platform filters together."""
        with app.app_context():
            # Create active and inactive entities
            active_entity = Entity(name="Active Multi", type="company", to_scrape=True)
            inactive_entity = Entity(name="Inactive Multi", type="company", to_scrape=False)
            db.session.add_all([active_entity, inactive_entity])
            db.session.flush()
            
            # Create multiple pages with different combinations
            active_instagram = Page(
                uuid=uuid4(),
                name="active_instagram",
                link="https://instagram.com/active1",
                platform="instagram",
                entity_id=active_entity.id
            )
            active_facebook = Page(
                uuid=uuid4(),
                name="active_facebook",
                link="https://facebook.com/active1",
                platform="facebook",
                entity_id=active_entity.id
            )
            inactive_instagram = Page(
                uuid=uuid4(),
                name="inactive_instagram",
                link="https://instagram.com/inactive1",
                platform="instagram",
                entity_id=inactive_entity.id
            )
            db.session.add_all([active_instagram, active_facebook, inactive_instagram])
            db.session.commit()
            
            # Query with platform filter
            result = PageRepository.get_pages_by_ids(
                [active_instagram.uuid, active_facebook.uuid, inactive_instagram.uuid],
                platform="instagram"
            )
            
            # Should only return active Instagram page
            assert len(result) == 1
            assert result[0].uuid == active_instagram.uuid
            assert result[0].platform == "instagram"
            assert result[0].entity.to_scrape is True
            
            # Cleanup
            db.session.delete(active_instagram)
            db.session.delete(active_facebook)
            db.session.delete(inactive_instagram)
            db.session.delete(active_entity)
            db.session.delete(inactive_entity)
            db.session.commit()

    def test_handles_none_platform_parameter(self, app):
        """Should handle None as platform parameter (no platform filter)."""
        with app.app_context():
            # Create entity and pages
            entity = Entity(name="None Platform Test", type="company", to_scrape=True)
            db.session.add(entity)
            db.session.flush()
            
            page = Page(
                uuid=uuid4(),
                name="test_page",
                link="https://instagram.com/nonetest",
                platform="instagram",
                entity_id=entity.id
            )
            db.session.add(page)
            db.session.commit()
            
            # Query with explicit None
            result = PageRepository.get_pages_by_ids([page.uuid], platform=None)
            
            assert len(result) == 1
            assert result[0].uuid == page.uuid
            
            # Cleanup
            db.session.delete(page)
            db.session.delete(entity)
            db.session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
