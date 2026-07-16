#!/usr/bin/env python3
"""
Simple script to test the scraping API endpoints.
This is a manual integration test to verify everything works.
"""
import os
import sys
import requests
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:5000"  # Change to your server URL
# No hardcoded default — set SCRAPING_API_KEY in the environment before running.
API_KEY = os.environ["SCRAPING_API_KEY"]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def test_fetch_posts():
    """Test fetching posts for scraping."""
    print("\n" + "="*60)
    print("TEST 1: Fetch Posts for Scraping")
    print("="*60)
    
    url = f"{BASE_URL}/api/scraping/posts"
    
    # Test without filters
    print(f"\n→ GET {url}")
    response = requests.get(url, headers=headers)
    
    print(f"← Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"✓ Success!")
        print(f"  Session ID: {data['data']['session_id']}")
        print(f"  Posts Count: {data['data']['count']}")
        print(f"  Sample Post: {data['data']['posts'][0] if data['data']['posts'] else 'No posts'}")
        return data['data']['session_id']
    else:
        print(f"✗ Failed: {data.get('error', 'Unknown error')}")
        return None


def test_fetch_posts_with_filter():
    """Test fetching posts with platform filter."""
    print("\n" + "="*60)
    print("TEST 2: Fetch Posts with Platform Filter")
    print("="*60)
    
    url = f"{BASE_URL}/api/scraping/posts?platform=instagram"
    
    print(f"\n→ GET {url}")
    response = requests.get(url, headers=headers)
    
    print(f"← Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"✓ Success!")
        print(f"  Instagram Posts Count: {data['data']['count']}")
    else:
        print(f"✗ Failed: {data.get('error', 'Unknown error')}")


def test_insert_comments(session_id=None):
    """Test inserting comments."""
    print("\n" + "="*60)
    print("TEST 3: Insert Comments")
    print("="*60)
    
    url = f"{BASE_URL}/api/scraping/comments"
    
    # Sample comment data
    payload = {
        "session_id": session_id,
        "comments": [
            {
                "page_id": "123e4567-e89b-12d3-a456-426614174000",
                "platform": "instagram",
                "post_id": "C12345678",
                "id": f"test_comment_{int(datetime.now().timestamp())}",
                "text": "This is a test comment from the API test script",
                "username": "test_user",
                "timestamp": int(datetime.now().timestamp()),
                "likes": 5,
                "is_reply": False
            }
        ]
    }
    
    print(f"\n→ POST {url}")
    print(f"  Payload: {payload}")
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"← Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"✓ Success!")
        print(f"  Inserted: {data['data']['inserted']}")
        print(f"  Skipped: {data['data']['skipped']}")
        print(f"  Total: {data['data']['total']}")
    else:
        print(f"✗ Failed: {data.get('error', 'Unknown error')}")


def test_get_session(session_id):
    """Test getting session details."""
    if not session_id:
        print("\n⊘ Skipping session test (no session ID)")
        return
    
    print("\n" + "="*60)
    print("TEST 4: Get Session Details")
    print("="*60)
    
    url = f"{BASE_URL}/api/scraping/sessions/{session_id}"
    
    print(f"\n→ GET {url}")
    response = requests.get(url, headers=headers)
    
    print(f"← Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"✓ Success!")
        print(f"  Session ID: {data['data']['session_id']}")
        print(f"  Status: {data['data']['status']}")
        print(f"  Posts Fetched: {data['data']['posts_fetched']}")
        print(f"  Comments Inserted: {data['data']['comments_inserted']}")
        print(f"  Created At: {data['data']['created_at']}")
    else:
        print(f"✗ Failed: {data.get('error', 'Unknown error')}")


def test_rate_limiting():
    """Test rate limiting (will fail after 100 requests)."""
    print("\n" + "="*60)
    print("TEST 5: Rate Limiting")
    print("="*60)
    print("Note: This requires 100+ requests and is disabled by default")
    print("Uncomment the code below to test rate limiting")
    
    # Uncomment to test rate limiting
    # url = f"{BASE_URL}/api/scraping/posts"
    # for i in range(105):
    #     response = requests.get(url, headers=headers)
    #     if response.status_code == 429:
    #         print(f"✓ Rate limit hit after {i+1} requests")
    #         print(f"  Error: {response.json()['error']}")
    #         break
    # else:
    #     print(f"✗ Rate limit not enforced after 105 requests")


def test_authentication():
    """Test authentication failures."""
    print("\n" + "="*60)
    print("TEST 6: Authentication")
    print("="*60)
    
    url = f"{BASE_URL}/api/scraping/posts"
    
    # Test without auth header
    print("\n→ GET without Authorization header")
    response = requests.get(url)
    print(f"← Status: {response.status_code}")
    
    if response.status_code == 401:
        print(f"✓ Correctly rejected (401)")
    else:
        print(f"✗ Should have rejected with 401")
    
    # Test with wrong API key
    print("\n→ GET with wrong API key")
    bad_headers = {"Authorization": "Bearer wrong-api-key"}
    response = requests.get(url, headers=bad_headers)
    print(f"← Status: {response.status_code}")
    
    if response.status_code == 401:
        print(f"✓ Correctly rejected (401)")
    else:
        print(f"✗ Should have rejected with 401")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("SCRAPING API INTEGRATION TESTS")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {API_KEY[:20]}...")
    
    try:
        # Run tests
        session_id = test_fetch_posts()
        test_fetch_posts_with_filter()
        test_insert_comments(session_id)
        test_get_session(session_id)
        test_rate_limiting()
        test_authentication()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)
    
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Error: Could not connect to {BASE_URL}")
        print("Make sure the Flask server is running!")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
