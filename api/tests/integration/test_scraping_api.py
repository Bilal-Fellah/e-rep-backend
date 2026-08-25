# Integration tests for scraping API endpoints.
import os
import pytest
from datetime import datetime, timedelta, date
from api.models.post_model import PostMV
from api.models.comment_model import Comment
from api.models.scraping_session_model import ScrapingSession
from api.models.scraping_post_result_model import ScrapingPostResult
from api import db


@pytest.fixture
def api_key():
    """Set and return test API key."""
    test_key = "test-scraping-api-key-12345"
    os.environ["SCRAPING_API_KEY"] = test_key
    return test_key


@pytest.fixture
def auth_headers(api_key):
    """Return authorization headers with API key."""
    return {"Authorization": f"Bearer {api_key}"}


@pytest.fixture
def admin_jwt_headers(app):
    """Return authorization headers with an admin JWT token."""
    from api.models.user_model import User
    from api.services.auth_service import AuthService
    
    with app.app_context():
        user = User.query.filter_by(email="test_admin_scraping@example.com").first()
        if not user:
            user = User(
                first_name="Test",
                last_name="Admin",
                email="test_admin_scraping@example.com",
                role="admin",
                is_verified=True,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
        tokens = AuthService.issue_token_pair(user)
        return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def registered_jwt_headers(app):
    """Return authorization headers with a registered user JWT token."""
    from api.models.user_model import User
    from api.services.auth_service import AuthService
    
    with app.app_context():
        user = User.query.filter_by(email="test_registered_scraping@example.com").first()
        if not user:
            user = User(
                first_name="Test",
                last_name="Registered",
                email="test_registered_scraping@example.com",
                role="registered",
                is_verified=True,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
        tokens = AuthService.issue_token_pair(user)
        return {"Authorization": f"Bearer {tokens['access_token']}"}



@pytest.fixture
def sample_posts(app):
    """Create sample posts in the database for testing."""
    with app.app_context():
        # Create posts from yesterday's snapshot
        yesterday = date.today() - timedelta(days=1)
        yesterday_datetime = datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=12)
        
        posts = [
            PostMV(
                page_id="123e4567-e89b-12d3-a456-426614174000",
                platform="instagram",
                post_id="C12345678",
                url="https://instagram.com/p/C12345678",
                created_at=datetime.now() - timedelta(days=2),
                recorded_at=yesterday_datetime,  # Yesterday's snapshot
                caption="Test post 1",
                likes=100,
                comments=10
            ),
            PostMV(
                page_id="123e4567-e89b-12d3-a456-426614174001",
                platform="facebook",
                post_id="FB123456",
                url="https://facebook.com/posts/FB123456",
                created_at=datetime.now() - timedelta(days=3),
                recorded_at=yesterday_datetime,  # Yesterday's snapshot
                caption="Test post 2",
                likes=200,
                comments=20
            ),
            PostMV(
                page_id="123e4567-e89b-12d3-a456-426614174002",
                platform="instagram",
                post_id="C87654321",
                url="https://instagram.com/p/C87654321",
                created_at=datetime.now() - timedelta(days=1),
                recorded_at=datetime.now(),  # Today's snapshot (should NOT be included)
                caption="Test post 3 - today",
                likes=50,
                comments=5
            )
        ]
        
        for post in posts:
            db.session.add(post)
        db.session.commit()
        
        yield posts
        
        # Cleanup
        for post in posts:
            db.session.delete(post)
        db.session.commit()


class TestApifyProfileScraping:
    """Tests for GET /api/scraping/apify_profile_scraping endpoint."""
    
    def test_apify_profiles_requires_auth(self, client):
        """Test that endpoint requires API key."""
        response = client.get("/api/scraping/apify_profile_scraping")
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert "API key" in data["error"]
    
    def test_apify_profiles_no_failed_pages(self, client, auth_headers):
        """Test when there are no failed pages today."""
        response = client.get("/api/scraping/apify_profile_scraping", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        assert "profiles" in data["data"]
        assert "count" in data["data"]
        assert "platform" in data["data"]
        assert "scraping_issues" in data["data"]
        assert data["data"]["platform"] == "all"
    
    def test_apify_profiles_invalid_platform(self, client, auth_headers):
        """Test invalid platform parameter."""
        response = client.get(
            "/api/scraping/apify_profile_scraping?platform=invalid",
            headers=auth_headers
        )
        assert response.status_code == 400
        
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid platform" in data["error"]
    
    def test_apify_profiles_with_platform_filter(self, client, auth_headers):
        """Test platform filtering."""
        response = client.get(
            "/api/scraping/apify_profile_scraping?platform=instagram",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["platform"] == "instagram"
        # If there are profiles, they should all be instagram
        for profile in data["data"]["profiles"]:
            assert profile["platform"] == "instagram"
    
    def test_apify_profiles_filters_inactive_entities(self, client, auth_headers, app):
        """
        Task 8.2: Verify active entity filtering works correctly.
        
        Test that profiles belonging to entities with to_scrape=False are correctly
        excluded from the response.
        
        Creates failed pages_history for both active and inactive entities,
        calls API endpoint, and verifies only active entity profiles are returned.
        """
        from api.models.page_model import Page
        from api.models.page_history_model import PageHistory
        from api.models.entity_model import Entity
        from uuid import uuid4
        
        # Setup: Create active and inactive entities with pages and failed history
        with app.app_context():
            # Create active entity with failed page history
            active_entity = Entity(
                name="Active Entity",
                type="company",
                to_scrape=True  # Active for scraping
            )
            db.session.add(active_entity)
            db.session.flush()
            
            active_page = Page(
                uuid=uuid4(),
                name="active_instagram",
                link="https://instagram.com/active_entity",
                platform="instagram",
                entity_id=active_entity.id
            )
            db.session.add(active_page)
            db.session.flush()
            
            # Create failed pages_history for active entity (missing comments)
            # datetime.utcnow(), not datetime.now(): the route this feeds
            # (get_failed_pages_for_today) windows on UTC ("yesterday 22:00
            # UTC to now"), so a local-time value drifts outside that window
            # by the local UTC offset near day boundaries.
            active_history = PageHistory(
                page_id=active_page.uuid,
                recorded_at=datetime.utcnow(),
                data={
                    "posts": [
                        {
                            "id": "post_1",
                            "likes": 100,
                            # Missing "comments" field - this makes it a failed scrape
                        }
                    ]
                }
            )
            db.session.add(active_history)
            
            # Create inactive entity with failed page history
            inactive_entity = Entity(
                name="Inactive Entity",
                type="company",
                to_scrape=False  # Inactive - should be filtered out
            )
            db.session.add(inactive_entity)
            db.session.flush()
            
            inactive_page = Page(
                uuid=uuid4(),
                name="inactive_instagram",
                link="https://instagram.com/inactive_entity",
                platform="instagram",
                entity_id=inactive_entity.id
            )
            db.session.add(inactive_page)
            db.session.flush()
            
            # Create failed pages_history for inactive entity (missing likes)
            inactive_history = PageHistory(
                page_id=inactive_page.uuid,
                recorded_at=datetime.utcnow(),
                data={
                    "posts": [
                        {
                            "id": "post_2",
                            "comments": 50,
                            # Missing "likes" field - this makes it a failed scrape
                        }
                    ]
                }
            )
            db.session.add(inactive_history)
            
            db.session.commit()
            
            active_page_id = str(active_page.uuid)
            inactive_page_id = str(inactive_page.uuid)
        
        try:
            # Call API endpoint
            response = client.get(
                "/api/scraping/apify_profile_scraping",
                headers=auth_headers
            )
            
            # Verify response
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            
            # Extract profile page IDs
            profile_page_ids = [p["name"] for p in data["data"]["profiles"]]
            
            # Verify only active entity profile is returned
            assert "active_instagram" in profile_page_ids
            assert "inactive_instagram" not in profile_page_ids
            
            # Verify entity filtering by checking entity details
            active_profiles = [p for p in data["data"]["profiles"] if p["name"] == "active_instagram"]
            assert len(active_profiles) == 1
            assert active_profiles[0]["entity_name"] == "Active Entity"
            assert active_profiles[0]["platform"] == "instagram"
            
            # Verify no inactive entity profiles
            inactive_profiles = [p for p in data["data"]["profiles"] if p["entity_name"] == "Inactive Entity"]
            assert len(inactive_profiles) == 0
            
        finally:
            # Cleanup
            with app.app_context():
                from uuid import UUID
                PageHistory.query.filter(
                    PageHistory.page_id.in_([UUID(active_page_id), UUID(inactive_page_id)])
                ).delete(synchronize_session=False)
                Page.query.filter(
                    Page.uuid.in_([UUID(active_page_id), UUID(inactive_page_id)])
                ).delete(synchronize_session=False)
                Entity.query.filter(
                    Entity.name.in_(["Active Entity", "Inactive Entity"])
                ).delete(synchronize_session=False)
                db.session.commit()


class TestFetchPosts:
    """Tests for GET /api/scraping/posts endpoint."""
    
    def test_fetch_posts_requires_auth(self, client):
        """Test that endpoint requires API key."""
        response = client.get("/api/scraping/posts")
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert "API key" in data["error"]
    
    def test_fetch_posts_invalid_api_key(self, client):
        """Test that invalid API key is rejected."""
        headers = {"Authorization": "Bearer invalid-key"}
        response = client.get("/api/scraping/posts", headers=headers)
        assert response.status_code == 401
    
    def test_fetch_posts_success(self, client, auth_headers, sample_posts):
        """Test successful post fetching with session creation."""
        response = client.get("/api/scraping/posts", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        assert "session_id" in data["data"]
        assert "posts" in data["data"]
        assert "count" in data["data"]
        
        # Returns all 3 available posts that need scraping today
        assert data["data"]["count"] == 3
        assert len(data["data"]["posts"]) == 3
    
    def test_fetch_posts_with_platform_filter(self, client, auth_headers, sample_posts):
        """Test platform filtering."""
        response = client.get(
            "/api/scraping/posts?platform=instagram",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        # 2 instagram posts in sample_posts
        assert data["data"]["count"] == 2
        for p in data["data"]["posts"]:
            assert p["platform"] == "instagram"

    def test_fetch_posts_with_recorded_date_filter(self, client, auth_headers, sample_posts):
        """Test recorded_start_date and recorded_end_date filtering."""
        from datetime import date, timedelta
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        
        # Filter for posts recorded yesterday
        response = client.get(
            f"/api/scraping/posts?recorded_start_date={yesterday_str}T00:00:00Z&recorded_end_date={yesterday_str}T23:59:59Z",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["count"] == 2
    
    def test_fetch_posts_invalid_platform(self, client, auth_headers):
        """Test invalid platform parameter."""
        response = client.get(
            "/api/scraping/posts?platform=invalid",
            headers=auth_headers
        )
        assert response.status_code == 400
        
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid platform" in data["error"]
    
    def test_fetch_posts_creates_session_record(self, client, auth_headers, sample_posts, app):
        """Test that session record is created in database."""
        response = client.get("/api/scraping/posts", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.get_json()
        session_id = data["data"]["session_id"]
        
        # Verify session exists in database
        with app.app_context():
            session = ScrapingSession.query.filter_by(session_id=session_id).first()
            assert session is not None
            assert session.posts_fetched == 3
            assert session.status == "pending"


class TestInsertComments:
    """Tests for POST /api/scraping/comments endpoint."""
    
    def test_insert_comments_requires_auth(self, client):
        """Test that endpoint requires API key."""
        response = client.post("/api/scraping/comments", json={"comments": []})
        assert response.status_code == 401
    
    def test_insert_comments_success(self, client, auth_headers, sample_posts, app):
        """Test successful comment insertion."""
        comments_data = {
            "comments": [
                {
                    "page_id": "123e4567-e89b-12d3-a456-426614174000",
                    "platform": "instagram",
                    "post_id": "C12345678",
                    "id": "18064830815724115",
                    "text": "@tatweer.digital شكرا",
                    "username": "malek_natsheh99",
                    "timestamp": 1783787046,
                    "likes": 0,
                    "is_reply": True,
                    "parent_id": "18094999820577949"
                }
            ]
        }
        
        response = client.post(
            "/api/scraping/comments",
            json=comments_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["inserted"] == 1
        assert data["data"]["skipped"] == 0
        assert data["data"]["total"] == 1
        
        # Verify comment was inserted
        with app.app_context():
            comment = Comment.query.filter_by(comment_id="18064830815724115").first()
            assert comment is not None
            assert comment.text == "@tatweer.digital شكرا"
            assert comment.author_username == "malek_natsheh99"
            assert comment.likes_count == 0
            assert comment.parent_comment_id == "18094999820577949"
    
    def test_insert_comments_with_duplicates(self, client, auth_headers, sample_posts, app):
        """Test duplicate comment detection."""
        comments_data = {
            "comments": [
                {
                    "page_id": "123e4567-e89b-12d3-a456-426614174000",
                    "platform": "instagram",
                    "post_id": "C12345678",
                    "id": "comment_001",
                    "text": "First comment",
                    "username": "user1",
                    "timestamp": 1783787046,
                    "likes": 5
                }
            ]
        }
        
        # Insert first time
        response1 = client.post(
            "/api/scraping/comments",
            json=comments_data,
            headers=auth_headers
        )
        assert response1.status_code == 200
        data1 = response1.get_json()
        assert data1["data"]["inserted"] == 1
        assert data1["data"]["skipped"] == 0
        
        # Insert same comment again
        response2 = client.post(
            "/api/scraping/comments",
            json=comments_data,
            headers=auth_headers
        )
        assert response2.status_code == 200
        data2 = response2.get_json()
        assert data2["data"]["inserted"] == 0
        assert data2["data"]["skipped"] == 1
    
    def test_insert_comments_validation_error(self, client, auth_headers):
        """Test validation of missing required fields."""
        comments_data = {
            "comments": [
                {
                    "page_id": "123e4567-e89b-12d3-a456-426614174000",
                    "platform": "instagram",
                    "post_id": "C12345678",
                    # Missing 'id' field
                    "text": "Test comment",
                    "username": "user1",
                    "timestamp": 1783787046
                }
            ]
        }
        
        response = client.post(
            "/api/scraping/comments",
            json=comments_data,
            headers=auth_headers
        )
        assert response.status_code == 400
        
        data = response.get_json()
        assert data["success"] is False
        assert "missing required field" in data["error"]
        assert "'id'" in data["error"]
    
    def test_insert_comments_empty_array(self, client, auth_headers):
        """Test that an empty comments array is accepted (posts with no comments)."""
        response = client.post(
            "/api/scraping/comments",
            json={"comments": []},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["inserted"] == 0
        assert data["data"]["skipped"] == 0
        assert data["data"]["total"] == 0
    
    def test_insert_comments_with_session_id(self, client, auth_headers, sample_posts, app):
        """Test comment insertion with session tracking."""
        # Create a session first
        with app.app_context():
            from api.repositories.scraping_session_repository import ScrapingSessionRepository
            session = ScrapingSessionRepository.create(posts_fetched=2)
            session_id = session.session_id
            db.session.commit()
        
        comments_data = {
            "session_id": session_id,
            "comments": [
                {
                    "page_id": "123e4567-e89b-12d3-a456-426614174000",
                    "platform": "instagram",
                    "post_id": "C12345678",
                    "id": "comment_with_session",
                    "text": "Test comment",
                    "username": "user1",
                    "timestamp": 1783787046
                }
            ]
        }
        
        response = client.post(
            "/api/scraping/comments",
            json=comments_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify session was updated
        with app.app_context():
            session = ScrapingSession.query.filter_by(session_id=session_id).first()
            assert session.comments_inserted == 1


class TestGetSessionDetails:
    """Tests for GET /api/scraping/sessions/{session_id} endpoint."""
    
    def test_get_session_requires_auth(self, client):
        """Test that endpoint requires API key."""
        response = client.get("/api/scraping/sessions/test-session-id")
        assert response.status_code == 401
    
    def test_get_session_success(self, client, auth_headers, app):
        """Test successful session retrieval."""
        # Create a session
        with app.app_context():
            from api.repositories.scraping_session_repository import ScrapingSessionRepository
            session = ScrapingSessionRepository.create(posts_fetched=10)
            session_id = session.session_id
            db.session.commit()
        
        response = client.get(
            f"/api/scraping/sessions/{session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["session_id"] == session_id
        assert data["data"]["posts_fetched"] == 10
        assert data["data"]["comments_inserted"] == 0
        assert data["data"]["status"] == "pending"
    
    def test_get_session_not_found(self, client, auth_headers):
        """Test 404 for non-existent session."""
        response = client.get(
            "/api/scraping/sessions/non-existent-id",
            headers=auth_headers
        )
        assert response.status_code == 404
        
        data = response.get_json()
        assert data["success"] is False
        assert "not found" in data["error"]


class TestCompleteSession:
    """Tests for POST /api/scraping/sessions/{session_id}/complete endpoint."""
    
    def test_complete_session_requires_auth(self, client):
        """Test that endpoint requires API key."""
        response = client.post("/api/scraping/sessions/test-id/complete")
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert "API key" in data["error"]
    
    def test_complete_session_success(self, client, auth_headers, app):
        """Test successfully completing a pending session."""
        with app.app_context():
            from api.repositories.scraping_session_repository import ScrapingSessionRepository
            session = ScrapingSessionRepository.create(posts_fetched=5)
            session_id = session.session_id
            db.session.commit()
        
        response = client.post(
            f"/api/scraping/sessions/{session_id}/complete",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["session_id"] == session_id
        assert data["data"]["status"] == "completed"
        assert data["data"]["completed_at"] is not None
        assert data["data"]["posts_fetched"] == 5
        
        # Verify in database
        with app.app_context():
            session = ScrapingSession.query.filter_by(session_id=session_id).first()
            assert session.status == "completed"
            assert session.completed_at is not None
    
    def test_complete_session_already_completed(self, client, auth_headers, app):
        """Test that completing an already-completed session returns 400."""
        with app.app_context():
            from api.repositories.scraping_session_repository import ScrapingSessionRepository
            session = ScrapingSessionRepository.create(posts_fetched=3)
            session_id = session.session_id
            db.session.commit()
        
        # Complete it once
        client.post(
            f"/api/scraping/sessions/{session_id}/complete",
            headers=auth_headers
        )
        
        # Try to complete again
        response = client.post(
            f"/api/scraping/sessions/{session_id}/complete",
            headers=auth_headers
        )
        assert response.status_code == 400
        
        data = response.get_json()
        assert data["success"] is False
        assert "cannot be completed" in data["error"]
        assert "completed" in data["error"]
    
    def test_complete_session_not_found(self, client, auth_headers):
        """Test 404 for non-existent session."""
        response = client.post(
            "/api/scraping/sessions/non-existent-id/complete",
            headers=auth_headers
        )
        assert response.status_code == 404
        
        data = response.get_json()
        assert data["success"] is False
        assert "not found" in data["error"]
    
    def test_complete_session_with_inserted_comments(self, client, auth_headers, app, sample_posts):
        """Test that completing a session reflects the correct comments_inserted count."""
        with app.app_context():
            from api.repositories.scraping_session_repository import ScrapingSessionRepository
            session = ScrapingSessionRepository.create(posts_fetched=1)
            session_id = session.session_id
            db.session.commit()
        
        # Insert 1 comment with the session_id
        client.post(
            "/api/scraping/comments",
            json={
                "session_id": session_id,
                "comments": [
                    {
                        "page_id": "123e4567-e89b-12d3-a456-426614174000",
                        "platform": "instagram",
                        "post_id": "C12345678",
                        "id": "complete_test_comment",
                        "text": "Test comment for completion",
                        "username": "user1",
                        "timestamp": 1783787046
                    }
                ]
            },
            headers=auth_headers
        )
        
        # Now complete the session
        response = client.post(
            f"/api/scraping/sessions/{session_id}/complete",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["data"]["comments_inserted"] == 1
        assert data["data"]["status"] == "completed"


class TestRateLimiting:
    """Tests for rate limiting functionality."""
    
    def test_rate_limit_enforced(self, client, api_key, monkeypatch):
        """Test that rate limit is enforced after 100 requests."""
        import os
        # Mock the rate limit to a lower value for testing
        from api.utils import api_key_auth
        monkeypatch.setattr(api_key_auth, "RATE_LIMIT_REQUESTS", 2)
        
        # Clear the rate limit store before testing
        api_key_auth.rate_limit_store.clear()
        
        # Use a unique API key for this test to avoid interference
        unique_api_key = "unique-test-key-rate-limit"
        os.environ["SCRAPING_API_KEY"] = unique_api_key
        headers = {"Authorization": f"Bearer {unique_api_key}"}
        
        # First request - should succeed
        response1 = client.get("/api/scraping/posts", headers=headers)
        assert response1.status_code in [200, 500]  # May fail due to no posts, but not rate limited
        
        # Second request - should succeed
        response2 = client.get("/api/scraping/posts", headers=headers)
        assert response2.status_code in [200, 500]
        
        # Third request - should be rate limited
        response3 = client.get("/api/scraping/posts", headers=headers)
        assert response3.status_code == 429
        
        data = response3.get_json()
        assert data["success"] is False
        assert "Rate limit exceeded" in data["error"]


class TestGetTodayPostsStatus:
    """Tests for GET /api/scraping/posts/today-status endpoint."""
    
    def test_get_today_status_requires_auth(self, client):
        """Test that endpoint requires auth token."""
        response = client.get("/api/scraping/posts/today-status")
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert "token" in data["error"]
        
    def test_get_today_status_forbidden_for_registered(self, client, registered_jwt_headers):
        """Test that registered users are forbidden (403)."""
        response = client.get(
            "/api/scraping/posts/today-status",
            headers=registered_jwt_headers
        )
        assert response.status_code == 403
        data = response.get_json()
        assert data["success"] is False
        assert "Insufficient permissions" in data["error"]
        
    def test_get_today_status_success(self, client, admin_jwt_headers, app):
        """Test retrieving today status, categorizing into scraped and pending."""
        yesterday = date.today() - timedelta(days=1)
        yesterday_datetime = datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=12)

        page_id = "999e4567-e89b-12d3-a456-426614174999"
        platform = "instagram"
        post_id_1 = "POST_STATUS_SCRAPED"
        post_id_2 = "POST_STATUS_PENDING"

        with app.app_context():
            # Create two unique posts
            post_scraped = PostMV(
                page_id=page_id,
                platform=platform,
                post_id=post_id_1,
                url=f"https://instagram.com/p/{post_id_1}",
                created_at=datetime.now() - timedelta(days=2),
                recorded_at=yesterday_datetime,
                caption="Scraped post test",
                likes=100,
                comments=10
            )
            post_pending = PostMV(
                page_id=page_id,
                platform=platform,
                post_id=post_id_2,
                url=f"https://instagram.com/p/{post_id_2}",
                created_at=datetime.now() - timedelta(days=2),
                recorded_at=yesterday_datetime,
                caption="Pending post test",
                likes=200,
                comments=20
            )
            db.session.add(post_scraped)
            db.session.add(post_pending)

            # Add one comment today for post_scraped
            comment = Comment(
                page_id=page_id,
                platform=platform,
                post_id=post_id_1,
                comment_id="status_comment_1",
                text="Great post!",
                author_username="test_user",
                comment_timestamp=datetime.now(),
                recorded_at=datetime.now()
            )
            db.session.add(comment)

            # Mark post_scraped as done via ScrapingPostResult
            spr = ScrapingPostResult(
                page_id=page_id,
                platform=platform,
                post_id=post_id_1,
                comments_count=1,
                scraped_at=datetime.now()
            )
            db.session.add(spr)
            db.session.commit()

        try:
            # Get today status
            response = client.get(
                "/api/scraping/posts/today-status",
                headers=admin_jwt_headers
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True

            res_data = data["data"]
            assert "scraped_posts" in res_data
            assert "pending_posts" in res_data

            # Filter the lists to only include our test posts to be 100% immune to other tests
            our_scraped = [p for p in res_data["scraped_posts"] if p["post_id"] == post_id_1]
            our_pending = [p for p in res_data["pending_posts"] if p["post_id"] == post_id_2]

            assert len(our_scraped) == 1
            assert len(our_pending) == 1

            # Verify details
            assert our_scraped[0]["scraped_comments_count"] == 1
            assert our_scraped[0]["expected_comments"] == 10
            assert our_scraped[0]["url"] == f"https://instagram.com/p/{post_id_1}"

            assert our_pending[0]["scraped_comments_count"] == 0
            assert our_pending[0]["expected_comments"] == 20
            assert our_pending[0]["url"] == f"https://instagram.com/p/{post_id_2}"

        finally:
            # Clean up posts, comment, and post result
            with app.app_context():
                ScrapingPostResult.query.filter_by(post_id=post_id_1).delete()
                Comment.query.filter_by(comment_id="status_comment_1").delete()
                PostMV.query.filter(PostMV.post_id.in_([post_id_1, post_id_2])).delete()
                db.session.commit()

    def test_get_today_status_with_platform_filter(self, client, admin_jwt_headers, app):
        """Test retrieving today status with a platform filter."""
        yesterday = date.today() - timedelta(days=1)
        yesterday_datetime = datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=12)

        page_id = "999e4567-e89b-12d3-a456-426614174999"
        platform = "youtube"  # Use a platform different from other tests to isolate
        post_id = "YT_STATUS_TEST"

        with app.app_context():
            post = PostMV(
                page_id=page_id,
                platform=platform,
                post_id=post_id,
                url=f"https://youtube.com/watch?v={post_id}",
                created_at=datetime.now() - timedelta(days=2),
                recorded_at=yesterday_datetime,
                caption="YT test",
                likes=150,
                comments=15
            )
            db.session.add(post)

            comment = Comment(
                page_id=page_id,
                platform=platform,
                post_id=post_id,
                comment_id="status_comment_yt",
                text="Great video!",
                author_username="test_user",
                comment_timestamp=datetime.now(),
                recorded_at=datetime.now()
            )
            db.session.add(comment)

            # Mark as done via ScrapingPostResult
            spr = ScrapingPostResult(
                page_id=page_id,
                platform=platform,
                post_id=post_id,
                comments_count=1,
                scraped_at=datetime.now()
            )
            db.session.add(spr)
            db.session.commit()

        try:
            # Query for platform=youtube
            response = client.get(
                "/api/scraping/posts/today-status?platform=youtube",
                headers=admin_jwt_headers
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True

            res_data = data["data"]
            assert res_data["platform_filter"] == "youtube"
            assert res_data["total_count"] == 1
            assert res_data["scraped_count"] == 1
            assert res_data["pending_count"] == 0
            assert res_data["scraped_posts"][0]["post_id"] == post_id

        finally:
            with app.app_context():
                ScrapingPostResult.query.filter_by(post_id=post_id).delete()
                Comment.query.filter_by(comment_id="status_comment_yt").delete()
                PostMV.query.filter_by(post_id=post_id).delete()
                db.session.commit()

    def test_get_today_status_invalid_platform(self, client, admin_jwt_headers):
        """Test GET with invalid platform parameter."""
        response = client.get(
            "/api/scraping/posts/today-status?platform=invalid",
            headers=admin_jwt_headers
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid platform" in data["error"]

    def test_get_today_status_invalid_date(self, client, admin_jwt_headers):
        """Test GET with invalid date parameter."""
        response = client.get(
            "/api/scraping/posts/today-status?date=invalid-date",
            headers=admin_jwt_headers
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid date format" in data["error"]

    def test_get_today_status_invalid_start_date(self, client, admin_jwt_headers):
        """Test GET with invalid start_date parameter."""
        response = client.get(
            "/api/scraping/posts/today-status?start_date=invalid-date",
            headers=admin_jwt_headers
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Invalid start_date format" in data["error"]

    def test_get_today_status_with_start_date_filter(self, client, admin_jwt_headers, app):
        """Test retrieving today status with a start_date filter."""
        yesterday = date.today() - timedelta(days=1)
        yesterday_datetime = datetime.combine(yesterday, datetime.min.time()) + timedelta(hours=12)
        
        page_id = "999e4567-e89b-12d3-a456-426614174999"
        platform = "youtube"
        post_old_id = "YT_OLD_POST"
        post_new_id = "YT_NEW_POST"
        
        # We will filter for posts created after start_date (today - 3 days)
        start_date_val = (date.today() - timedelta(days=3)).isoformat()
        
        with app.app_context():
            # Created 5 days ago (should be filtered out by start_date)
            post_old = PostMV(
                page_id=page_id,
                platform=platform,
                post_id=post_old_id,
                url=f"https://youtube.com/watch?v={post_old_id}",
                created_at=datetime.now() - timedelta(days=5),
                recorded_at=yesterday_datetime,
                caption="Old post",
                likes=150,
                comments=15
            )
            # Created 1 day ago (should be included by start_date)
            post_new = PostMV(
                page_id=page_id,
                platform=platform,
                post_id=post_new_id,
                url=f"https://youtube.com/watch?v={post_new_id}",
                created_at=datetime.now() - timedelta(days=1),
                recorded_at=yesterday_datetime,
                caption="New post",
                likes=200,
                comments=20
            )
            db.session.add(post_old)
            db.session.add(post_new)
            db.session.commit()
            
        try:
            # Query for platform=youtube & start_date
            response = client.get(
                f"/api/scraping/posts/today-status?platform=youtube&start_date={start_date_val}",
                headers=admin_jwt_headers
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            
            res_data = data["data"]
            assert res_data["platform_filter"] == "youtube"
            assert res_data["start_date_filter"] == start_date_val
            assert res_data["total_count"] == 1
            assert res_data["pending_count"] == 1
            assert len(res_data["pending_posts"]) == 1
            assert res_data["pending_posts"][0]["post_id"] == post_new_id
            
        finally:
            with app.app_context():
                PostMV.query.filter(PostMV.post_id.in_([post_old_id, post_new_id])).delete()
                db.session.commit()


class TestProfileFlow:
    """Integration tests for GET /api/scraping/own_scraper/profiles and
    POST /api/scraping/profile-info — the profile-info counterpart to
    TestFetchPosts/TestInsertComments above. See
    api/docs/scraping_profiles.md for the contract this implements."""

    def test_fetch_profiles_requires_auth(self, client):
        response = client.get("/api/scraping/own_scraper/profiles?platform=instagram")
        assert response.status_code == 401

    def test_fetch_profiles_requires_platform(self, client, auth_headers):
        response = client.get("/api/scraping/own_scraper/profiles", headers=auth_headers)
        assert response.status_code == 400

    def test_fetch_profiles_rejects_unsupported_platform(self, client, auth_headers):
        response = client.get("/api/scraping/own_scraper/profiles?platform=tiktok", headers=auth_headers)
        assert response.status_code == 400
        assert "tiktok" in response.get_json()["error"]

    def test_fetch_then_insert_profile_round_trip(self, client, auth_headers, app):
        from api.models.entity_model import Entity
        from api.models.page_model import Page
        from api.models.page_history_model import PageHistory

        with app.app_context():
            entity = Entity(name="Profile Flow Test Co", type="company", to_scrape=True)
            db.session.add(entity)
            db.session.commit()
            page = Page(
                name="Profile Flow Page",
                link="https://instagram.com/profile_flow_test_page",
                platform="instagram",
                entity_id=entity.id,
            )
            db.session.add(page)
            db.session.commit()
            page_id = str(page.uuid)

        try:
            fetch_resp = client.get("/api/scraping/own_scraper/profiles?platform=instagram", headers=auth_headers)
            assert fetch_resp.status_code == 200
            fetch_data = fetch_resp.get_json()["data"]
            assert page_id in {p["page_id"] for p in fetch_data["profiles"]}
            session_id = fetch_data["session_id"]

            insert_resp = client.post(
                "/api/scraping/profile-info",
                headers=auth_headers,
                json={
                    "session_id": session_id,
                    "profiles": [
                        {
                            "page_id": page_id,
                            "platform": "instagram",
                            "account_id": page_id,
                            "followers": 4242,
                            "biography": "integration test bio",
                            "profile_image_link": "https://example/img.jpg",
                        }
                    ],
                    "profile_results": [
                        {"page_id": page_id, "platform": "instagram", "account_id": page_id}
                    ],
                },
            )
            assert insert_resp.status_code == 200
            insert_data = insert_resp.get_json()["data"]
            assert insert_data["inserted"] == 1

            with app.app_context():
                import uuid as uuid_mod

                history = (
                    PageHistory.query.filter_by(page_id=uuid_mod.UUID(page_id))
                    .order_by(PageHistory.id.desc())
                    .first()
                )
                assert history is not None
                assert history.source == "own_scraper"
                assert history.data["followers"] == 4242

            # Fetching again today must now exclude this page -- it's done.
            refetch_resp = client.get("/api/scraping/own_scraper/profiles?platform=instagram", headers=auth_headers)
            refetch_ids = {p["page_id"] for p in refetch_resp.get_json()["data"]["profiles"]}
            assert page_id not in refetch_ids
        finally:
            with app.app_context():
                import uuid as uuid_mod

                from api.models.scraping_profile_result_model import ScrapingProfileResult

                PageHistory.query.filter_by(page_id=uuid_mod.UUID(page_id)).delete()
                ScrapingProfileResult.query.filter_by(page_id=page_id).delete()
                Page.query.filter_by(uuid=uuid_mod.UUID(page_id)).delete()
                Entity.query.filter_by(name="Profile Flow Test Co").delete()
                db.session.commit()

    def test_insert_profile_info_rejects_missing_fields(self, client, auth_headers):
        response = client.post(
            "/api/scraping/profile-info",
            headers=auth_headers,
            json={"profiles": [{"page_id": "p1", "platform": "instagram"}]},  # no account_id
        )
        assert response.status_code == 400
        assert response.get_json()["success"] is False


