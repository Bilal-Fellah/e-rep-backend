"""Check alert navigation data accuracy"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json

def main():
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        user="bilal",
        password="chupakabra",
        database="erep-db"
    )
    
    print("=" * 80)
    print("ALERT NAVIGATION DATA CHECK")
    print("=" * 80)
    
    user_id = 14  # Change if needed
    
    # Get user's recent alerts
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT ua.id as user_alert_id, ua.status,
                   ae.id as event_id, ae.event_type, ae.comment_pk, 
                   ae.post_id, ae.page_id, ae.platform, ae.label, ae.payload
            FROM user_alerts ua
            JOIN alert_events ae ON ua.event_id = ae.id
            WHERE ua.user_id = %s
              AND ae.event_type = 'negative_comment'
            ORDER BY ua.created_at DESC
            LIMIT 5
        """, (user_id,))
        
        alerts = cur.fetchall()
        
        if not alerts:
            print(f"\n❌ No alerts found for user {user_id}")
            conn.close()
            return
        
        print(f"\n✅ Found {len(alerts)} recent alerts for user {user_id}")
        
        for i, alert in enumerate(alerts, 1):
            print(f"\n{'=' * 80}")
            print(f"ALERT #{i}")
            print(f"{'=' * 80}")
            
            print(f"\nAlert Info:")
            print(f"  User Alert ID: {alert['user_alert_id']}")
            print(f"  Event ID: {alert['event_id']}")
            print(f"  Status: {alert['status']}")
            print(f"  Label: {alert['label']} ({'Negative' if alert['label'] in [0,1] else 'Positive'})")
            
            print(f"\nNavigation Data:")
            print(f"  Platform: {alert['platform']}")
            print(f"  Page ID: {alert['page_id']}")
            print(f"  Post ID: {alert['post_id']}")
            print(f"  Comment PK: {alert['comment_pk']}")
            
            # Get the actual comment
            cur.execute("""
                SELECT c.id, c.post_id, c.page_id, c.text, c.label, c.author_username,
                       c.platform, c.recorded_at
                FROM comments c
                WHERE c.id = %s
            """, (alert['comment_pk'],))
            
            comment = cur.fetchone()
            
            if not comment:
                print(f"\n  ❌ ERROR: Comment {alert['comment_pk']} NOT FOUND in database!")
                continue
            
            print(f"\nActual Comment Data:")
            print(f"  Comment ID: {comment['id']}")
            print(f"  Post ID in DB: {comment['post_id']}")
            print(f"  Page ID in DB: {comment['page_id']}")
            print(f"  Platform in DB: {comment['platform']}")
            print(f"  Label in DB: {comment['label']} ({'Negative' if comment['label'] in [0,1] else 'Positive'})")
            print(f"  Author: {comment['author_username']}")
            print(f"  Text: {comment['text'][:100]}...")
            
            # Check if post_id matches
            if comment['post_id'] != alert['post_id']:
                print(f"\n  ⚠️  WARNING: Post ID mismatch!")
                print(f"      Alert says: {alert['post_id']}")
                print(f"      Comment says: {comment['post_id']}")
            else:
                print(f"\n  ✅ Post ID matches")
            
            # Check if page_id matches
            if str(comment['page_id']) != alert['page_id']:
                print(f"\n  ⚠️  WARNING: Page ID mismatch!")
                print(f"      Alert says: {alert['page_id']}")
                print(f"      Comment says: {comment['page_id']}")
            else:
                print(f"\n  ✅ Page ID matches")
            
            # Check if label matches
            if comment['label'] != alert['label']:
                print(f"\n  ⚠️  WARNING: Label changed!")
                print(f"      Alert says: {alert['label']}")
                print(f"      Comment now has: {comment['label']}")
                print(f"      This comment was relabeled after the alert was created!")
            else:
                print(f"\n  ✅ Label matches")
            
            # Get post details to verify
            cur.execute("""
                SELECT post_id, caption, platform, page_id
                FROM posts_mv
                WHERE post_id = %s AND platform = %s
                LIMIT 1
            """, (alert['post_id'], alert['platform']))
            
            post = cur.fetchone()
            
            if post:
                print(f"\nPost Exists in Database:")
                print(f"  Post ID: {post['post_id']}")
                print(f"  Platform: {post['platform']}")
                print(f"  Caption: {post['caption'][:80] if post['caption'] else 'None'}...")
            else:
                print(f"\n  ⚠️  Post {alert['post_id']} not found in posts_mv!")
            
            # Check how many negative comments are on this post
            cur.execute("""
                SELECT COUNT(*) as count
                FROM comments
                WHERE post_id = %s
                  AND label IN (0, 1)
            """, (alert['post_id'],))
            
            neg_count = cur.fetchone()['count']
            
            # Check total comments on this post
            cur.execute("""
                SELECT COUNT(*) as count
                FROM comments
                WHERE post_id = %s
            """, (alert['post_id'],))
            
            total_count = cur.fetchone()['count']
            
            print(f"\nComments on This Post:")
            print(f"  Total Comments: {total_count}")
            print(f"  Negative Comments (label 0 or 1): {neg_count}")
            
            if neg_count == 0 and total_count > 0:
                print(f"\n  ⚠️  WARNING: No negative comments found on this post!")
                print(f"      But the alert references comment {alert['comment_pk']}")
                print(f"      This suggests the comment label was changed after the alert.")
            
            # Get payload
            if alert['payload']:
                print(f"\nAlert Payload:")
                print(f"  {json.dumps(alert['payload'], indent=2)}")
    
    conn.close()
    
    print(f"\n{'=' * 80}")
    print("ANALYSIS COMPLETE")
    print(f"{'=' * 80}")
    
    print(f"\nPossible Issues:")
    print(f"  1. Comment labels changed after alerts were created")
    print(f"  2. Frontend might not be loading comments correctly")
    print(f"  3. Frontend might be filtering out negative comments")
    print(f"  4. Post ID navigation might be incorrect in frontend")

if __name__ == "__main__":
    main()
