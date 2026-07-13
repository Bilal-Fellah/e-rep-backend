# Integration tests for scraping API endpoints.
import os
import pytest
from datetime import datetime, timedelta, date
from api.models.post_model import PostMV
from api.models.comment_model import Comment
from api.models.scraping_session_model import ScrapingSession
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
        
        # Should only return 2 posts from yesterday's snapshot (not today's)
        assert data["data"]["count"] == 2
        assert len(data["data"]["posts"]) == 2
    
    def test_fetch_posts_with_platform_filter(self, client, auth_headers, sample_posts):
        """Test platform filtering."""
        response = client.get(
            "/api/scraping/posts?platform=instagram",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["success"] is True
        # Only 1 instagram post from yesterday
        assert data["data"]["count"] == 1
        assert data["data"]["posts"][0]["platform"] == "instagram"
    
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
            assert session.posts_fetched == 2
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
            # Clean up posts and comment
            with app.app_context():
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


