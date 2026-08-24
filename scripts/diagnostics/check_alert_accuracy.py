"""Check alert accuracy and duplicate issues"""
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
    print("ALERT ACCURACY AND DUPLICATE CHECK")
    print("=" * 80)
    
    # Issue 1: Check if alert events have correct comment references
    print("\n" + "-" * 80)
    print("ISSUE 1: Checking Alert Event Accuracy")
    print("-" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get negative comment alert events
        cur.execute("""
            SELECT ae.id, ae.event_type, ae.comment_pk, ae.post_id, ae.page_id, 
                   ae.label, ae.dedupe_key, ae.event_at
            FROM alert_events ae
            WHERE ae.event_type = 'negative_comment'
            ORDER BY ae.created_at DESC
            LIMIT 20
        """)
        events = cur.fetchall()
        
        print(f"\n✅ Found {len(events)} recent negative comment events")
        
        if events:
            print(f"\n  Checking first 10 events for accuracy...")
            
            mismatched = 0
            missing_comments = 0
            
            for event in events[:10]:
                # Check if the comment exists and has the expected label
                cur.execute("""
                    SELECT c.id, c.text, c.label, c.post_id, c.page_id
                    FROM comments c
                    WHERE c.id = %s
                """, (event['comment_pk'],))
                
                comment = cur.fetchone()
                
                if not comment:
                    print(f"\n  ❌ Event {event['id']}: Comment {event['comment_pk']} NOT FOUND!")
                    missing_comments += 1
                    continue
                
                # Check if label matches
                if comment['label'] != event['label']:
                    print(f"\n  ⚠️  Event {event['id']}: LABEL MISMATCH")
                    print(f"      Comment PK: {event['comment_pk']}")
                    print(f"      Event Label: {event['label']}")
                    print(f"      Comment Label: {comment['label']}")
                    print(f"      Comment Text: {comment['text'][:80]}...")
                    mismatched += 1
                
                # Check if post_id matches
                if comment['post_id'] != event['post_id']:
                    print(f"\n  ⚠️  Event {event['id']}: POST_ID MISMATCH")
                    print(f"      Event Post ID: {event['post_id']}")
                    print(f"      Comment Post ID: {comment['post_id']}")
                
                # Check if page_id matches
                if str(comment['page_id']) != event['page_id']:
                    print(f"\n  ⚠️  Event {event['id']}: PAGE_ID MISMATCH")
                    print(f"      Event Page ID: {event['page_id']}")
                    print(f"      Comment Page ID: {comment['page_id']}")
            
            if mismatched == 0 and missing_comments == 0:
                print(f"\n  ✅ All checked events are accurate!")
            else:
                print(f"\n  Summary:")
                print(f"    - Missing comments: {missing_comments}")
                print(f"    - Label mismatches: {mismatched}")
    
    # Issue 2: Check for duplicate alerts
    print("\n" + "-" * 80)
    print("ISSUE 2: Checking for Duplicate Alerts")
    print("-" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check for duplicate events (same comment, different events)
        cur.execute("""
            SELECT comment_pk, label, COUNT(*) as count
            FROM alert_events
            WHERE event_type = 'negative_comment'
              AND comment_pk IS NOT NULL
            GROUP BY comment_pk, label
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 10
        """)
        
        duplicates = cur.fetchall()
        
        if duplicates:
            print(f"\n  ⚠️  Found {len(duplicates)} comments with duplicate events!")
            
            for dup in duplicates:
                print(f"\n  Comment PK: {dup['comment_pk']}, Label: {dup['label']}, Events: {dup['count']}")
                
                # Get the dedupe keys for this comment
                cur.execute("""
                    SELECT id, dedupe_key, event_at, created_at
                    FROM alert_events
                    WHERE event_type = 'negative_comment'
                      AND comment_pk = %s
                      AND label = %s
                    ORDER BY created_at
                """, (dup['comment_pk'], dup['label']))
                
                events_for_comment = cur.fetchall()
                
                for e in events_for_comment:
                    print(f"    - Event ID: {e['id']}, Dedupe Key: {e['dedupe_key']}")
                    print(f"      Event At: {e['event_at']}, Created At: {e['created_at']}")
        else:
            print(f"\n  ✅ No duplicate events found!")
    
    # Issue 3: Check for duplicate user alerts (same user, same event, multiple alerts)
    print("\n" + "-" * 80)
    print("ISSUE 3: Checking for Duplicate User Alerts")
    print("-" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT user_id, event_id, COUNT(*) as count
            FROM user_alerts
            GROUP BY user_id, event_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 10
        """)
        
        dup_alerts = cur.fetchall()
        
        if dup_alerts:
            print(f"\n  ⚠️  Found {len(dup_alerts)} user/event combinations with duplicate alerts!")
            
            for dup in dup_alerts:
                print(f"\n  User ID: {dup['user_id']}, Event ID: {dup['event_id']}, Alerts: {dup['count']}")
                
                # Get details
                cur.execute("""
                    SELECT ua.id, ua.rule_id, ua.status, ua.created_at
                    FROM user_alerts ua
                    WHERE ua.user_id = %s AND ua.event_id = %s
                    ORDER BY ua.created_at
                """, (dup['user_id'], dup['event_id']))
                
                alerts = cur.fetchall()
                
                for a in alerts:
                    print(f"    - Alert ID: {a['id']}, Rule ID: {a['rule_id']}, Status: {a['status']}")
        else:
            print(f"\n  ✅ No duplicate user alerts found!")
    
    # Issue 4: Check comment label changes
    print("\n" + "-" * 80)
    print("ISSUE 4: Checking for Comment Label Changes")
    print("-" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get comments that have events
        cur.execute("""
            SELECT DISTINCT c.id, c.label, c.text, c.recorded_at, c.label_updated_at
            FROM comments c
            JOIN alert_events ae ON ae.comment_pk = c.id
            WHERE ae.event_type = 'negative_comment'
            ORDER BY c.label_updated_at DESC NULLS LAST
            LIMIT 20
        """)
        
        comments = cur.fetchall()
        
        print(f"\n  Checking {len(comments)} comments that have events...")
        
        negative_count = 0
        positive_count = 0
        
        for comment in comments[:10]:
            if comment['label'] in [0, 1]:
                negative_count += 1
            elif comment['label'] in [2, 3]:
                positive_count += 1
                print(f"\n  ⚠️  Comment {comment['id']} has POSITIVE label but has negative_comment event!")
                print(f"      Current Label: {comment['label']}")
                print(f"      Label Updated: {comment['label_updated_at']}")
                print(f"      Text: {comment['text'][:80]}...")
        
        print(f"\n  Summary:")
        print(f"    - Comments with negative labels (0,1): {negative_count}")
        print(f"    - Comments with positive labels (2,3): {positive_count}")
        
        if positive_count > 0:
            print(f"\n  ⚠️  WARNING: {positive_count} comments changed from negative to positive!")
            print(f"      This means labels were updated AFTER events were created.")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
