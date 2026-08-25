"""Check timing of rule creation vs event creation"""
import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        user="bilal",
        password="chupakabra",
        database="erep-db"
    )
    
    print("=" * 80)
    print("TIMING ANALYSIS")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get rule creation time
        cur.execute("""
            SELECT id, created_at
            FROM alert_rules
            WHERE id = 2
        """)
        rule = cur.fetchone()
        
        print(f"\nRule 2 created at: {rule['created_at']}")
        
        # Get events for entity 93
        cur.execute("""
            SELECT id, created_at, event_at
            FROM alert_events
            WHERE entity_id = 93 AND event_type = 'negative_comment'
            ORDER BY created_at DESC
        """)
        events = cur.fetchall()
        
        print(f"\n✅ Found {len(events)} events for entity 93")
        print(f"\nEvents created:")
        
        events_before_rule = 0
        events_after_rule = 0
        
        for event in events[:10]:  # Show first 10
            if event['created_at'] < rule['created_at']:
                status = "❌ BEFORE rule"
                events_before_rule += 1
            else:
                status = "✅ AFTER rule"
                events_after_rule += 1
            print(f"  Event {event['id']}: {event['created_at']} - {status}")
        
        print(f"\n{'=' * 80}")
        print(f"SUMMARY:")
        print(f"  Events created BEFORE rule: {events_before_rule} (won't trigger alerts)")
        print(f"  Events created AFTER rule: {events_after_rule} (SHOULD trigger alerts)")
        print(f"{'=' * 80}")
        
        # Now check if the detector has run AFTER the rule was created
        cur.execute("""
            SELECT detector_name, cursor_ts, updated_at
            FROM alert_detector_checkpoints
            WHERE detector_name = 'negative_comment'
        """)
        checkpoint = cur.fetchone()
        
        print(f"\nDetector checkpoint:")
        print(f"  Last run at: {checkpoint['updated_at']}")
        print(f"  Cursor: {checkpoint['cursor_ts']}")
        
        if checkpoint['updated_at'] > rule['created_at']:
            print(f"  ✅ Detector HAS run after rule creation")
            print(f"  ⚠️  But still no alerts were created!")
            print(f"\n  This suggests a bug in the fanout logic!")
        else:
            print(f"  ❌ Detector has NOT run since rule creation")
            print(f"  Run the detector again to create alerts")
        
        # Check if there are any negative comments AFTER the checkpoint
        cur.execute("""
            SELECT COUNT(*) as count
            FROM comments c
            JOIN pages p ON c.page_id::uuid = p.uuid
            WHERE p.entity_id = 93 
              AND c.label IN (0, 1)
              AND COALESCE(c.label_updated_at, c.recorded_at) > %s
        """, (checkpoint['cursor_ts'],))
        new_comments = cur.fetchone()
        
        print(f"\n  New comments after checkpoint: {new_comments['count']}")
    
    conn.close()

if __name__ == "__main__":
    main()
