# API key authentication utilities.
import os
import time
from functools import wraps
from flask import request
from api.routes.main import error_response


# Simple in-memory rate limiting (per API key)
# Structure: {api_key: {"count": int, "reset_time": float}}
rate_limit_store = {}
RATE_LIMIT_REQUESTS = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds


def require_api_key(func):
    """
    Decorator to enforce API key authentication.
    Expects API key in Authorization header: "Bearer <api_key>"
    Also enforces rate limiting (100 requests per minute per API key).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract API key from Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return error_response("Invalid or missing API key", 401)
        
        # Expected format: "Bearer <api_key>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return error_response("Invalid or missing API key", 401)
        
        provided_key = parts[1]
        expected_key = os.getenv("SCRAPING_API_KEY")
        
        if not expected_key:
            return error_response("Invalid or missing API key", 401)
        
        if provided_key != expected_key:
    
            return error_response("Invalid or missing API key", 401)
        
        # Rate limiting check
        current_time = time.time()
        
        if provided_key in rate_limit_store:
            limit_data = rate_limit_store[provided_key]
            
            # Reset counter if window has passed
            if current_time >= limit_data["reset_time"]:
                rate_limit_store[provided_key] = {
                    "count": 1,
                    "reset_time": current_time + RATE_LIMIT_WINDOW
                }
            else:
                # Check if limit exceeded
                if limit_data["count"] >= RATE_LIMIT_REQUESTS:
                    retry_after = int(limit_data["reset_time"] - current_time)
                    return error_response(
                        f"Rate limit exceeded. Try again in {retry_after} seconds.", 
                        429
                    )
                
                # Increment counter
                limit_data["count"] += 1
        else:
            # First request for this API key
            rate_limit_store[provided_key] = {
                "count": 1,
                "reset_time": current_time + RATE_LIMIT_WINDOW
            }
        
        # Proceed to route handler
        return func(*args, **kwargs)
    
    return wrapper
