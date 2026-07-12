# Requirements Document

## Introduction

This feature provides API endpoints for an external scraping service to integrate with the e-rep backend system. The external service performs comment scraping on posts and needs to:
1. Fetch a list of posts from the database daily
2. Insert scraped comments back into the database after processing

The API must be accurate about data tracking (posts fetched, comments inserted) and guarantee zero data loss during the process.

## Glossary

- **External_Scraping_Service**: The third-party service that performs comment scraping on social media posts
- **API_System**: The Flask backend application providing integration endpoints
- **Post**: A social media post entity identified by composite key (page_id, platform, post_id)
- **Comment**: A user comment on a social media post with metadata (text, author, timestamp, etc.)
- **Fetch_Request**: A request from the External_Scraping_Service to retrieve posts for scraping
- **Comment_Batch**: A collection of scraped comments submitted by the External_Scraping_Service
- **Scraping_Session**: A unique identifier tracking a specific scraping operation from fetch to insertion

## Requirements

### Requirement 1: Daily Post Fetching API

**User Story:** As an external scraping service, I want to fetch a list of posts from the database through an API endpoint, so that I can scrape comments for those posts.

#### Acceptance Criteria

1. THE API_System SHALL provide an endpoint to retrieve posts for scraping
2. WHEN a Fetch_Request is received, THE API_System SHALL return all posts matching the request criteria
3. WHEN a Fetch_Request specifies a platform filter, THE API_System SHALL return only posts from that platform
4. WHEN a Fetch_Request specifies a date range filter, THE API_System SHALL return only posts created within that range
5. THE API_System SHALL include all necessary post identifiers (page_id, platform, post_id) in the response
6. THE API_System SHALL include post metadata (url, created_at, caption) in the response
7. THE API_System SHALL generate a unique Scraping_Session identifier for each Fetch_Request
8. THE API_System SHALL record the Scraping_Session identifier, timestamp, and post count for tracking
9. WHEN no posts match the request criteria, THE API_System SHALL return an empty list with success status
10. THE API_System SHALL validate all query parameters before processing the request
11. IF invalid query parameters are provided, THEN THE API_System SHALL return a descriptive error message with HTTP 400 status

### Requirement 2: Comment Insertion API

**User Story:** As an external scraping service, I want to insert scraped comments back into the database through an API endpoint, so that the comments can be stored and analyzed.

#### Acceptance Criteria

1. THE API_System SHALL provide an endpoint to insert scraped comments
2. WHEN a Comment_Batch is received, THE API_System SHALL validate all required fields for each comment
3. THE API_System SHALL validate that each comment references a valid Post by composite key
4. IF any required field is missing or invalid, THEN THE API_System SHALL reject the entire Comment_Batch and return a descriptive error
5. THE API_System SHALL insert all comments in a Comment_Batch as a single atomic transaction
6. IF any comment insertion fails, THEN THE API_System SHALL rollback the entire transaction to prevent partial data
7. THE API_System SHALL record the number of comments successfully inserted
8. THE API_System SHALL associate inserted comments with the Scraping_Session identifier if provided
9. THE API_System SHALL return the count of successfully inserted comments in the response
10. THE API_System SHALL prevent duplicate comment insertion by checking comment identifiers
11. WHEN duplicate comments are detected, THE API_System SHALL skip duplicates and insert only new comments
12. THE API_System SHALL return a detailed summary indicating new comments inserted and duplicates skipped

### Requirement 3: Comment Data Model

**User Story:** As a developer, I want a database model for storing scraped comments, so that comments can be persisted and queried efficiently.

#### Acceptance Criteria

1. THE API_System SHALL define a Comment database model with all necessary fields
2. THE Comment model SHALL include a composite foreign key referencing the Post (page_id, platform, post_id)
3. THE Comment model SHALL include a unique comment_id field provided by the external platform
4. THE Comment model SHALL include comment text content
5. THE Comment model SHALL include comment author information (username, profile_url)
6. THE Comment model SHALL include comment timestamp (when the comment was posted)
7. THE Comment model SHALL include a recorded_at timestamp (when the comment was scraped)
8. THE Comment model SHALL include a likes count field
9. THE Comment model SHALL include a replies count field
10. THE Comment model SHALL include an optional parent_comment_id field for nested replies
11. THE Comment model SHALL include a JSON extra_data field for platform-specific metadata
12. THE Comment model SHALL enforce a unique constraint on (page_id, platform, post_id, comment_id)

### Requirement 4: Comment Repository

**User Story:** As a developer, I want a repository layer for comment data access, so that database operations are abstracted and testable.

#### Acceptance Criteria

1. THE API_System SHALL provide a CommentRepository class following the existing repository pattern
2. THE CommentRepository SHALL provide a method to insert a single comment
3. THE CommentRepository SHALL provide a method to bulk insert multiple comments in a transaction
4. THE CommentRepository SHALL provide a method to check if a comment exists by composite key
5. THE CommentRepository SHALL provide a method to retrieve comments for a specific post
6. THE CommentRepository SHALL provide a method to retrieve comment count for a specific post
7. THE CommentRepository SHALL provide a method to retrieve comments by scraping session
8. THE CommentRepository SHALL handle database exceptions and return appropriate error information

### Requirement 5: Scraping Session Tracking

**User Story:** As a system administrator, I want to track scraping sessions with metadata, so that I can audit and troubleshoot the scraping process.

#### Acceptance Criteria

1. THE API_System SHALL define a ScrapingSession database model
2. THE ScrapingSession model SHALL include a unique session_id
3. THE ScrapingSession model SHALL include a created_at timestamp
4. THE ScrapingSession model SHALL include a posts_fetched count
5. THE ScrapingSession model SHALL include a comments_inserted count
6. THE ScrapingSession model SHALL include a status field (pending, completed, failed)
7. THE ScrapingSession model SHALL include an optional error_message field
8. THE API_System SHALL create a new ScrapingSession record when posts are fetched
9. THE API_System SHALL update the ScrapingSession record when comments are inserted
10. THE API_System SHALL provide an endpoint to retrieve scraping session details

### Requirement 6: API Authentication and Authorization

**User Story:** As a system administrator, I want API endpoints secured with authentication, so that only authorized external services can access the system.

#### Acceptance Criteria

1. THE API_System SHALL require authentication for all scraping API endpoints
2. THE API_System SHALL support API key authentication for the External_Scraping_Service
3. THE API_System SHALL validate the API key on every request
4. IF an invalid or missing API key is provided, THEN THE API_System SHALL return HTTP 401 Unauthorized
5. THE API_System SHALL log all authenticated requests with timestamp and endpoint
6. THE API_System SHALL rate limit requests from the same API key to prevent abuse
7. IF rate limit is exceeded, THEN THE API_System SHALL return HTTP 429 Too Many Requests

### Requirement 7: API Documentation

**User Story:** As an external service developer, I want comprehensive API documentation, so that I can integrate with the scraping endpoints correctly.

#### Acceptance Criteria

1. THE API_System SHALL provide documentation for all scraping API endpoints in Markdown format
2. THE documentation SHALL include endpoint URLs and HTTP methods
3. THE documentation SHALL include all request parameters with types and descriptions
4. THE documentation SHALL include request body schemas with examples
5. THE documentation SHALL include all possible response formats with HTTP status codes
6. THE documentation SHALL include error response examples with explanations
7. THE documentation SHALL include authentication instructions
8. THE documentation SHALL include example curl commands for each endpoint

### Requirement 8: Comprehensive Testing

**User Story:** As a developer, I want comprehensive tests for the scraping API, so that the feature is reliable and maintainable.

#### Acceptance Criteria

1. THE API_System SHALL include unit tests for the CommentRepository class
2. THE API_System SHALL include unit tests for comment validation logic
3. THE API_System SHALL include integration tests for the post fetching endpoint
4. THE API_System SHALL include integration tests for the comment insertion endpoint
5. THE API_System SHALL include integration tests for transaction rollback on insertion failure
6. THE API_System SHALL include tests for duplicate comment detection
7. THE API_System SHALL include tests for authentication and authorization
8. THE API_System SHALL include tests for invalid input handling and error responses
9. THE API_System SHALL include tests for scraping session tracking
10. THE API_System SHALL achieve at least 90% code coverage for the scraping feature

### Requirement 9: Error Handling and Logging

**User Story:** As a system administrator, I want detailed error handling and logging, so that I can diagnose issues with the scraping integration.

#### Acceptance Criteria

1. THE API_System SHALL log all scraping API requests with timestamp, endpoint, and parameters
2. THE API_System SHALL log all database operations for comments and scraping sessions
3. WHEN a database error occurs, THE API_System SHALL log the full error details
4. WHEN a validation error occurs, THE API_System SHALL log the validation failures
5. THE API_System SHALL return user-friendly error messages without exposing internal details
6. THE API_System SHALL use appropriate HTTP status codes for all error responses
7. THE API_System SHALL log successful operations with summary statistics
8. THE API_System SHALL follow the existing logging patterns in the codebase

### Requirement 10: Data Integrity and Consistency

**User Story:** As a system administrator, I want guaranteed data integrity during comment insertion, so that no data is lost or corrupted.

#### Acceptance Criteria

1. THE API_System SHALL use database transactions for all comment insertion operations
2. THE API_System SHALL validate foreign key references before insertion
3. IF a referenced Post does not exist, THEN THE API_System SHALL reject the comment and log the error
4. THE API_System SHALL enforce all database constraints (unique, not null, foreign key)
5. THE API_System SHALL prevent race conditions during concurrent comment insertions
6. THE API_System SHALL validate data types and lengths before insertion
7. IF database constraints are violated, THEN THE API_System SHALL return a descriptive error message
8. THE API_System SHALL maintain referential integrity between Comments, Posts, and ScrapingSessions
