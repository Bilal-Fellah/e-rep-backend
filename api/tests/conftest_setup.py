"""
Pytest configuration file for test setup
"""

import os
import pytest

# Set up test environment variables BEFORE any imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("VPS_ADDRESS", "localhost")
os.environ.setdefault("VPS_DB_PORT", "5432")
os.environ.setdefault("DB_USER", "testuser")
os.environ.setdefault("DB_PWD", "testpass")
os.environ.setdefault("DB_NAME", "testdb")
os.environ.setdefault("FRONTEND_REDIRECT_URL", "http://localhost:3000")
os.environ.setdefault("FRONTEND_COOKIE_DOMAIN", "localhost")
os.environ.setdefault("COOKIE_SECURE", "false")
