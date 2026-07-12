#!/usr/bin/env python3
"""
Script to create the scraping tables in the database.
Run this after implementing the feature to create the comments and scraping_sessions tables.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api import create_app, db
from api.models.comment_model import Comment
from api.models.scraping_session_model import ScrapingSession


def create_tables():
    """Create the scraping-related tables."""
    app = create_app()
    
    with app.app_context():
        print("Creating scraping tables...")
        
        # Create only the new tables
        Comment.__table__.create(db.engine, checkfirst=True)
        ScrapingSession.__table__.create(db.engine, checkfirst=True)
        
        print("✓ Comments table created")
        print("✓ Scraping sessions table created")
        print("\nTables created successfully!")
        print("\nYou can now use the scraping API endpoints:")
        print("  - GET  /api/scraping/posts")
        print("  - POST /api/scraping/comments")
        print("  - GET  /api/scraping/sessions/{session_id}")


if __name__ == "__main__":
    create_tables()
