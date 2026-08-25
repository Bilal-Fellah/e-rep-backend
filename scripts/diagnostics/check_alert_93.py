"""Check alert rule and comments for entity 93"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    # Database connection
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        user="bilal",
        password="chupakabra",
        database="erep-db"
    )
    
    print("=" * 80)
    print("CHECKING ALERT RULE FOR ENTITY 93")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check alert rules for entity 93
        cur.execute("""
            SELECT id, user_id, name, event_type, is_active, entity_scope, 
                   cooldown_minutes, created_at
            FROM alert_rules
            WHERE entity_scope::text LIKE '%93%'
        """)
        rules = cur.fetchall()
        
        if not rules:
            print("\n❌ NO ALERT RULES FOUND FOR ENTITY 93")
        else:
            print(f"\n✅ Found {len(rules)} alert rule(s) for entity 93:")
            for rule in rules:
                print(f"\n  Rule ID: {rule['id']}")
                print(f"  User ID: {rule['user_id']}")
                print(f"  Name: {rule['name']}")
                print(f"  Event Type: {rule['event_type']}")
                print(f"  Is Active: {rule['is_active']}")
                print(f"  Entity Scope: {rule['entity_scope']}")
                print(f"  Cooldown: {rule['cooldown_minutes']} minutes")
                print(f"  Created: {rule['created_at']}")
    
    print("\n" + "=" * 80)
    print("CHECKING PAGES FOR ENTITY 93")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get pages for entity 93
        cur.execute("""
            SELECT uuid, entity_id, platform, name, link
            FROM pages
            WHERE entity_id = 93
        """)
        pages = cur.fetchall()
        
        if not pages:
            print("\n❌ NO PAGES FOUND FOR ENTITY 93")
        else:
            print(f"\n✅ Found {len(pages)} page(s) for entity 93:")
            for page in pages:
                print(f"\n  Page UUID: {page['uuid']}")
                print(f"  Platform: {page['platform']}")
                print(f"  Name: {page['name']}")
                print(f"  Link: {page['link']}")
    
    print("\n" + "=" * 80)
    print("CHECKING COMMENTS FOR ENTITY 93")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get comments for entity 93 pages with labels
        cur.execute("""
            SELECT c.id, c.page_id, c.text, c.label, c.confidence, 
                   c.recorded_at, c.label_updated_at, c.scraping_session_id
            FROM comments c
            JOIN pages p ON c.page_id::uuid = p.uuid
            WHERE p.entity_id = 93 
              AND c.label IS NOT NULL
            ORDER BY COALESCE(c.label_updated_at, c.recorded_at) DESC
            LIMIT 20
        """)
        comments = cur.fetchall()
        
        if not comments:
            print("\n❌ NO LABELED COMMENTS FOUND FOR ENTITY 93")
        else:
            print(f"\n✅ Found {len(comments)} labeled comment(s) (showing up to 20):")
            negative_count = sum(1 for c in comments if c['label'] in [0, 1])
            print(f"  Negative comments (label 0 or 1): {negative_count}")
            
            for i, comment in enumerate(comments[:5], 1):
                print(f"\n  Comment {i}:")
                print(f"    ID: {comment['id']}")
                print(f"    Page ID: {comment['page_id']}")
                print(f"    Label: {comment['label']} ({'Negative' if comment['label'] in [0, 1] else 'Positive'})")
                print(f"    Confidence: {comment['confidence']}")
                print(f"    Recorded: {comment['recorded_at']}")
                print(f"    Label Updated: {comment['label_updated_at']}")
                print(f"    Text: {comment['text'][:100]}...")
    
    print("\n" + "=" * 80)
    print("CHECKING ALERT DETECTOR CHECKPOINT")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check negative_comment detector checkpoint
        cur.execute("""
            SELECT detector_name, cursor_ts, updated_at
            FROM alert_detector_checkpoints
            WHERE detector_name = 'negative_comment'
        """)
        checkpoint = cur.fetchone()
        
        if not checkpoint:
            print("\n⚠️  NO CHECKPOINT FOR negative_comment DETECTOR")
        else:
            print(f"\n✅ Negative comment detector checkpoint:")
            print(f"  Cursor timestamp: {checkpoint['cursor_ts']}")
            print(f"  Updated at: {checkpoint['updated_at']}")
            
            # Check if there are comments after the checkpoint
            cur.execute("""
                SELECT COUNT(*) as count
                FROM comments c
                JOIN pages p ON c.page_id::uuid = p.uuid
                WHERE p.entity_id = 93 
                  AND c.label IN (0, 1)
                  AND COALESCE(c.label_updated_at, c.recorded_at) > %s
            """, (checkpoint['cursor_ts'],))
            new_comments = cur.fetchone()
            
            print(f"\n  Comments after checkpoint: {new_comments['count']}")
            
            if new_comments['count'] > 0:
                print("\n  ⚠️  There ARE comments after the checkpoint!")
                print("     The detector should have picked them up.")
            else:
                print("\n  ℹ️  No new comments after the checkpoint.")
                print("     This is why no new events were created.")
    
    print("\n" + "=" * 80)
    print("CHECKING ALERT EVENTS FOR ENTITY 93")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, event_type, severity, entity_id, label, 
                   event_at, created_at, dedupe_key
            FROM alert_events
            WHERE entity_id = 93
            ORDER BY created_at DESC
            LIMIT 10
        """)
        events = cur.fetchall()
        
        if not events:
            print("\n❌ NO ALERT EVENTS FOUND FOR ENTITY 93")
        else:
            print(f"\n✅ Found {len(events)} alert event(s) for entity 93:")
            for event in events:
                print(f"\n  Event ID: {event['id']}")
                print(f"  Type: {event['event_type']}")
                print(f"  Severity: {event['severity']}")
                print(f"  Label: {event['label']}")
                print(f"  Event at: {event['event_at']}")
                print(f"  Created at: {event['created_at']}")
    
    conn.close()
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
