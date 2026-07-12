# Implementation Plan: External Scraping Service API

## Overview

This implementation plan creates a secure API integration layer for an external scraping service to fetch posts and insert scraped comments. The approach follows the existing codebase patterns with a three-layer architecture (repository, service, routes) and emphasizes transactional safety, accurate tracking, and zero data loss.

## Tasks

- [ ] 1. Set up database models and core infrastructure
  - Create Comment and ScrapingSession ORM models
  - Define database schema with constraints and indexes
  - Set up API key authentication decorator
  - Create scraping routes blueprint
  - _Requirements: 3.1-3.12, 5.1-5.8, 6.1-6.7_

  - [ ] 1.1 Create Comment model
    - Define `api/models/comment_model.py` with Comment class
    - Include all fields: composite post key (page_id, platform, post_id), comment_id, text, author info, timestamps, metrics, parent_comment_id, scraping_session_id, extra_data
    - Add composite unique constraint on (page_id, platform, post_id, comment_id)
    - Add indexes on post lookup and session_id
    - _Requirements: 3.1-3.12_

  - [ ] 1.2 Create ScrapingSession model
    - Define `api/models/scraping_session_model.py` with ScrapingSession class
    - Include fields: session_id (UUID), created_at, completed_at, posts_fetched, comments_inserted, status, error_message
    - Add relationship to Comment model
    - Add check constraint for status enum (pending, completed, failed)
    - _Requirements: 5.1-5.8_

  - [ ] 1.3 Create API key authentication decorator
    - Define `api/utils/api_key_auth.py` with `require_api_key` decorator
    - Extract API key from Authorization header (Bearer token format)
    - Validate against SCRAPING_API_KEY environment variable
    - Implement in-memory rate limiting (100 requests per minute)
    - Return 401 for invalid/missing key, 429 for rate limit exceeded
    - Log all authentication attempts
    - _Requirements: 6.1-6.7_

  - [ ] 1.4 Create scraping routes blueprint
    - Define `api/routes/scraping_routes.py` with scraping_bp blueprint
    - Register blueprint error handlers using `register_blueprint_error_handlers`
    - Import and use `error_response`, `success_response`, `db_error_response` from `api.routes.main`
    - _Requirements: 6.1-6.7_

- [ ] 2. Checkpoint - Verify models and authentication setup
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Implement repository layer for data access
  - Build CommentRepository for CRUD operations
  - Build ScrapingSessionRepository for session tracking
  - Follow existing repository patterns with `@instrument_repository_class` decorator
  - _Requirements: 4.1-4.8_

  - [ ] 3.1 Create CommentRepository
    - Define `api/repositories/comment_repository.py` with CommentRepository class
    - Add `@instrument_repository_class` decorator
    - Implement `create(comment_data, commit=True)`: Insert single comment
    - Implement `bulk_create(comments_data, commit=True)`: Insert multiple comments, return (inserted_count, skipped_count)
    - Implement `exists(page_id, platform, post_id, comment_id)`: Check duplicate
    - Implement `get_by_composite_key(page_id, platform, post_id, comment_id)`: Fetch single comment
    - Implement `get_by_post(page_id, platform, post_id)`: Fetch all comments for post
    - Implement `get_by_session(session_id)`: Fetch comments by session
    - Implement `count_by_post(page_id, platform, post_id)`: Count comments for post
    - Handle SQLAlchemyError exceptions appropriately
    - _Requirements: 4.1-4.8_

  - [ ] 3.2 Create ScrapingSessionRepository
    - Define `api/repositories/scraping_session_repository.py` with ScrapingSessionRepository class
    - Add `@instrument_repository_class` decorator
    - Implement `create(posts_fetched, commit=True)`: Create new session with UUID
    - Implement `get_by_id(session_id)`: Fetch session by ID
    - Implement `update_status(session_id, status, error_message=None, commit=True)`: Update status
    - Implement `increment_comments(session_id, count, commit=True)`: Increment comments_inserted counter
    - Implement `complete_session(session_id, commit=True)`: Mark completed with timestamp
    - Implement `get_all(limit=100, offset=0)`: Fetch sessions with pagination
    - _Requirements: 5.1-5.10_

- [ ] 4. Implement service layer for business logic
  - Build ScrapingService with validation, session tracking, and transaction coordination
  - Follow existing service patterns with `@instrument_service_class` decorator
  - _Requirements: 1.1-1.11, 2.1-2.12, 10.1-10.8_

  - [ ] 4.1 Create ScrapingService with post fetching logic
    - Define `api/services/scraping_service.py` with ScrapingService class
    - Add `@instrument_service_class` decorator
    - Implement `fetch_posts_for_scraping(platform=None, start_date=None, end_date=None)`:
      - Use PostRepository to query posts_mv with filters
      - Create new ScrapingSession with posts count
      - Return dict with session_id, posts array, count
    - Parse and validate date parameters (ISO 8601 format)
    - _Requirements: 1.1-1.11_

  - [ ] 4.2 Add comment validation logic to ScrapingService
    - Implement `validate_comment_data(comment)`:
      - Check required fields: page_id, platform, post_id, comment_id, text, author_username, comment_timestamp
      - Validate data types (string, datetime, integer)
      - Return (is_valid, error_message) tuple
    - _Requirements: 2.2, 2.4_

  - [ ] 4.3 Add comment insertion logic to ScrapingService
    - Implement `insert_comment_batch(comments_data, session_id=None)`:
      - Validate all comments using validate_comment_data
      - Use CommentRepository.bulk_create for atomic insertion
      - Update ScrapingSession with comments_inserted count
      - Handle duplicates (skip and track skipped count)
      - Return dict with inserted, skipped, session_id
      - Wrap in transaction with rollback on failure
    - _Requirements: 2.1-2.12, 10.1-10.8_

  - [ ] 4.4 Add session details retrieval to ScrapingService
    - Implement `get_session_details(session_id)`:
      - Use ScrapingSessionRepository.get_by_id
      - Format as dict with all session fields
      - Return None if session not found
    - _Requirements: 5.10_

- [ ] 5. Checkpoint - Verify service layer logic
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement API routes and request handling
  - Build POST /api/scraping/comments endpoint
  - Build GET /api/scraping/posts endpoint
  - Build GET /api/scraping/sessions/{session_id} endpoint
  - Apply `@require_api_key` decorator to all endpoints
  - _Requirements: 1.1-1.11, 2.1-2.12, 5.10, 6.1-6.7, 9.1-9.8_

  - [ ] 6.1 Implement POST /api/scraping/comments endpoint
    - Add route handler in `api/routes/scraping_routes.py`
    - Apply `@require_api_key` decorator
    - Extract session_id and comments array from request body
    - Call ScrapingService.insert_comment_batch
    - Return success_response with inserted, skipped, total counts
    - Handle validation errors (400), database errors (500)
    - Log all operations using existing logging patterns
    - _Requirements: 2.1-2.12, 6.1-6.7, 9.1-9.8_

  - [ ] 6.2 Implement GET /api/scraping/posts endpoint
    - Add route handler in `api/routes/scraping_routes.py`
    - Apply `@require_api_key` decorator
    - Extract query parameters: platform, start_date, end_date
    - Call ScrapingService.fetch_posts_for_scraping with filters
    - Return success_response with session_id, posts array, count
    - Handle invalid query parameters (400)
    - Log all operations
    - _Requirements: 1.1-1.11, 6.1-6.7, 9.1-9.8_

  - [ ] 6.3 Implement GET /api/scraping/sessions/{session_id} endpoint
    - Add route handler in `api/routes/scraping_routes.py`
    - Apply `@require_api_key` decorator
    - Extract session_id from URL path
    - Call ScrapingService.get_session_details
    - Return success_response with session data
    - Return 404 if session not found
    - Log all operations
    - _Requirements: 5.10, 6.1-6.7, 9.1-9.8_

  - [ ] 6.4 Register scraping blueprint in main app
    - Update `api/__init__.py` or main app factory to import and register scraping_bp
    - Set URL prefix to `/api/scraping`
    - Ensure blueprint error handlers are registered
    - _Requirements: 6.1-6.7_

- [ ] 7. Create API documentation
  - Document all endpoints with request/response examples
  - Follow existing documentation patterns in api/docs/
  - _Requirements: 7.1-7.8_

  - [ ] 7.1 Create API documentation file
    - Create `api/docs/scraping_api.md`
    - Document POST /api/scraping/comments with request body schema, response formats, error codes
    - Document GET /api/scraping/posts with query parameters, response format, error codes
    - Document GET /api/scraping/sessions/{session_id} with response format, error codes
    - Include authentication instructions (Bearer token in Authorization header)
    - Add curl examples for each endpoint
    - Document rate limiting (100 requests per minute)
    - _Requirements: 7.1-7.8_

- [ ] 8. Write unit tests for repositories
  - Test CommentRepository CRUD operations
  - Test ScrapingSessionRepository operations
  - Follow existing test patterns in api/tests/integration/test_repos.py
  - _Requirements: 8.1-8.10_

  - [ ]* 8.1 Write unit tests for CommentRepository
    - Create `api/tests/unit/test_comment_repository.py`
    - Test `create`: Insert single comment with all fields
    - Test `create` with minimal fields (only required)
    - Test `bulk_create`: Insert multiple comments successfully
    - Test `bulk_create` with duplicates: Skip duplicates, insert new ones
    - Test `exists`: Check duplicate detection
    - Test `get_by_composite_key`: Fetch comment by composite key
    - Test `get_by_post`: Fetch all comments for a post
    - Test `get_by_session`: Fetch all comments for a session
    - Test `count_by_post`: Count comments for a post
    - Use monkeypatching for db.session as in existing tests
    - _Requirements: 8.1, 8.10_

  - [ ]* 8.2 Write unit tests for ScrapingSessionRepository
    - Create `api/tests/unit/test_scraping_session_repository.py`
    - Test `create`: Create new session with post count
    - Test `get_by_id`: Fetch session by ID
    - Test `update_status` to completed
    - Test `update_status` with error message
    - Test `increment_comments`: Increment comments counter
    - Test `complete_session`: Mark session as completed with timestamp
    - Test `get_all`: Fetch sessions with pagination
    - Use monkeypatching for db.session
    - _Requirements: 8.1, 8.10_

- [ ] 9. Write unit tests for service layer
  - Test ScrapingService validation and business logic
  - Mock repository calls
  - _Requirements: 8.1-8.10_

  - [ ]* 9.1 Write unit tests for ScrapingService
    - Create `api/tests/unit/test_scraping_service.py`
    - Test `validate_comment_data` with valid complete comment
    - Test `validate_comment_data` with missing required fields
    - Test `fetch_posts_for_scraping`: Session created on fetch
    - Test `fetch_posts_for_scraping` with platform filter
    - Test `fetch_posts_for_scraping` with date range filter
    - Test `insert_comment_batch`: All comments inserted successfully
    - Test `insert_comment_batch` with duplicates: Skip duplicates correctly
    - Test `insert_comment_batch` with validation failure: Reject invalid batch
    - Test `get_session_details`: Retrieve session information
    - Use monkeypatching to mock repository calls
    - _Requirements: 8.2, 8.10_

- [ ] 10. Write integration tests for API endpoints
  - Test complete request/response flows
  - Test authentication and error handling
  - Follow existing test patterns in api/tests/api/test_routes.py
  - _Requirements: 8.3-8.10_

  - [ ]* 10.1 Write integration tests for POST /api/scraping/comments
    - Create `api/tests/integration/test_scraping_api.py`
    - Test successful comment insertion: Complete end-to-end
    - Test comment insertion with duplicates: Duplicate handling
    - Test validation error: Invalid data rejection
    - Test missing API key: 401 response
    - Test invalid API key: 401 response
    - Test transaction rollback on failure
    - Test session update after insertion
    - Use Flask test client with app context
    - _Requirements: 8.3, 8.5, 8.7, 8.8, 8.10_

  - [ ]* 10.2 Write integration tests for GET /api/scraping/posts
    - Add tests to `api/tests/integration/test_scraping_api.py`
    - Test successful post fetch: Returns posts with session ID
    - Test platform filter: Platform filtering works
    - Test date filter: Date range filtering works
    - Test session record creation: Session persisted
    - Test missing API key: 401 response
    - Test invalid query parameters: 400 response
    - _Requirements: 8.3, 8.7, 8.8, 8.10_

  - [ ]* 10.3 Write integration tests for GET /api/scraping/sessions/{session_id}
    - Add tests to `api/tests/integration/test_scraping_api.py`
    - Test successful session retrieval: Returns session data
    - Test session not found: 404 response
    - Test missing API key: 401 response
    - _Requirements: 8.3, 8.7, 8.8, 8.10_

  - [ ]* 10.4 Write integration tests for authentication and rate limiting
    - Add tests to `api/tests/integration/test_scraping_api.py`
    - Test API key in Authorization header: Bearer format
    - Test rate limit enforcement: 429 after 100 requests
    - Test rate limit reset: Counter resets after 1 minute
    - _Requirements: 8.7, 8.10_

- [ ] 11. Add SCRAPING_API_KEY to environment configuration
  - Update `.env` file with SCRAPING_API_KEY variable
  - Document environment variable in README or deployment docs
  - _Requirements: 6.2, 6.3_

- [ ] 12. Final checkpoint - End-to-end validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after major milestones
- The implementation follows existing codebase patterns (repository → service → routes)
- All database operations use transactions with rollback on failure
- API key authentication is enforced on all endpoints
- Logging uses existing `instrument_repository_class` and `instrument_service_class` decorators
- Documentation follows the Markdown format in `api/docs/`
- Tests follow existing patterns with monkeypatching and Flask test client

## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1.1", "1.2"]
    },
    {
      "id": 1,
      "tasks": ["1.3", "1.4", "3.1", "3.2"]
    },
    {
      "id": 2,
      "tasks": ["4.1", "4.2"]
    },
    {
      "id": 3,
      "tasks": ["4.3", "4.4"]
    },
    {
      "id": 4,
      "tasks": ["6.1", "6.2", "6.3"]
    },
    {
      "id": 5,
      "tasks": ["6.4", "7.1", "11"]
    },
    {
      "id": 6,
      "tasks": ["8.1", "8.2", "9.1"]
    },
    {
      "id": 7,
      "tasks": ["10.1", "10.2", "10.3", "10.4"]
    }
  ]
}
```
