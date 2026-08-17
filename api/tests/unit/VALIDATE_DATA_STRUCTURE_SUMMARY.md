# validate_data_structure() Implementation Summary

## Overview
Implemented the `validate_data_structure()` helper function in `PageHistoryRepository` as specified in task 1.2 of the Apify Fallback Scraping spec.

## Location
- **File**: `api/repositories/page_history_repository.py`
- **Method**: `PageHistoryRepository.validate_data_structure(data: dict, platform: str) -> list[str]`

## Functionality
The function validates platform-specific JSONB data structures from the `pages_history` table to detect incomplete scraping.

### Platform-Specific Key Mapping
- **Instagram**: `posts` → checks for `likes` and `comments`
- **Facebook**: `posts` → checks for `likes` and `comments`
- **X (Twitter)**: `posts` → checks for `likes` and `comments`
- **TikTok**: `top_videos` → checks for `diggCount`/`likes` and `commentCount`/`comments`
- **LinkedIn**: `updates` → checks for `likes` and `comments`
- **YouTube**: `top_videos` → checks for `likes` and `comments`

### Engagement Field Variations Supported
The function recognizes multiple field name variations:
- **Likes**: `likes`, `likesCount`, `likeCount`, `diggCount`
- **Comments**: `comments`, `commentsCount`, `commentCount`

### Return Values
- **Empty list `[]`**: Data structure is valid (all required keys present)
- **Non-empty list**: Contains names of missing keys (e.g., `["posts"]`, `["likes", "comments"]`)
- **Special cases**: 
  - `["posts (empty)"]` when posts array exists but is empty
  - `["top_videos (empty)"]` when top_videos array exists but is empty
  - `["updates (empty)"]` when updates array exists but is empty

## Test Coverage
Created comprehensive test suites with **36 tests total**, all passing:

### Unit Tests (25 tests)
File: `api/tests/unit/test_page_history_repository.py`

Tests cover:
- Valid data structures for all 6 platforms
- Missing posts/top_videos/updates keys
- Empty posts arrays
- Missing engagement fields (likes, comments)
- Multiple engagement field name variations
- Edge cases (null data, non-array posts, null values vs zero values)
- Multi-post arrays (only first post checked)
- Unknown platforms (defaults to "posts")

### Example-Based Tests (11 tests)
File: `api/tests/unit/test_validate_data_structure_examples.py`

Tests cover realistic scenarios:
- Complete profile data for all platforms
- Incomplete scraping scenarios (timeout, rate limits)
- Alternate field name variations
- Real-world data structures

## Test Results
```
============================= test session starts =============================
platform win32 -- Python 3.13.6, pytest-9.0.2, pluggy-1.6.0
collected 36 items

test_page_history_repository.py::TestValidateDataStructure .......... [ 69%]
test_validate_data_structure_examples.py::TestValidateDataStructure.. [100%]

============================= 36 passed in 1.02s ==============================
```

## Implementation Details

### Algorithm
1. Maps platform to expected post array key (posts/top_videos/updates)
2. Checks if post array exists and is a valid list
3. Returns early if no posts array or empty array
4. Examines first post for required engagement fields
5. Checks multiple field name variations for likes and comments
6. Returns list of missing keys

### Key Features
- **Null safety**: Handles None data gracefully
- **Type checking**: Validates posts is a list, not other types
- **Field variation support**: Recognizes platform-specific field names
- **Zero value handling**: Treats 0 as valid (not missing)
- **Early exit optimization**: Stops checking if posts array missing
- **First-post validation**: Only checks first post (as per design spec)

## Usage Example
```python
from api.repositories.page_history_repository import PageHistoryRepository

# Valid Instagram data
data = {
    "posts": [
        {"post_id": "123", "likes": 100, "comments": 50}
    ]
}
result = PageHistoryRepository.validate_data_structure(data, "instagram")
# result = []  (empty list = valid)

# Invalid Instagram data (missing engagement fields)
data = {
    "posts": [
        {"post_id": "123", "caption": "Hello"}
    ]
}
result = PageHistoryRepository.validate_data_structure(data, "instagram")
# result = ["likes", "comments"]

# Missing posts array
data = {
    "followers": 1000,
    "biography": "My bio"
}
result = PageHistoryRepository.validate_data_structure(data, "instagram")
# result = ["posts"]
```

## Integration with get_failed_pages_for_today()
This helper function will be used by `PageHistoryRepository.get_failed_pages_for_today()` (Task 1.3) to identify which pages require fallback scraping via Apify.

## Compliance with Requirements
✅ **Requirement 1.1**: Create platform-specific validation for JSONB data field  
✅ **Requirement 1.2**: Check for missing posts/top_videos/updates keys  
✅ **Requirement 1.2**: Check for missing likes and comments fields within posts  
✅ **Requirement 1.2**: Support multiple engagement field name variations  
✅ **Requirement 1.2**: Return list of missing key names  

## Design Document Alignment
The implementation follows the **Platform-Specific Validation Algorithm** pseudocode from the design document exactly, including:
- Platform-specific posts key mapping
- Early exit on missing/empty posts array
- Engagement field variation checking
- Missing keys list accumulation
