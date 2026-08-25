"""Check user alerts for rule 2 and user 14"""
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
    print("CHECKING USER ALERTS FOR USER 14 (Owner of Rule 2)")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check user alerts
        cur.execute("""
            SELECT ua.id, ua.user_id, ua.event_id, ua.rule_id, 
                   ua.status, ua.created_at, ae.event_type, ae.entity_id, ae.label
            FROM user_alerts ua
            JOIN alert_events ae ON ua.event_id = ae.id
            WHERE ua.user_id = 14
            ORDER BY ua.created_at DESC
            LIMIT 20
        """)
        alerts = cur.fetchall()
        
        if not alerts:
            print("\n❌ NO USER ALERTS FOUND FOR USER 14")
            print("\n   This is the problem! Events were created but not distributed to the user.")
        else:
            print(f"\n✅ Found {len(alerts)} user alert(s) for user 14:")
            for alert in alerts:
                print(f"\n  Alert ID: {alert['id']}")
                print(f"  Event ID: {alert['event_id']}")
                print(f"  Rule ID: {alert['rule_id']}")
                print(f"  Status: {alert['status']}")
                print(f"  Event Type: {alert['event_type']}")
                print(f"  Entity ID: {alert['entity_id']}")
                print(f"  Label: {alert['label']}")
                print(f"  Created: {alert['created_at']}")
    
    print("\n" + "=" * 80)
    print("CHECKING IF EVENTS EXIST FOR ENTITY 93")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT COUNT(*) as count
            FROM alert_events
            WHERE entity_id = 93 AND event_type = 'negative_comment'
        """)
        result = cur.fetchone()
        print(f"\n✅ Found {result['count']} events for entity 93")
        
        # Check if any of these events have user alerts
        cur.execute("""
            SELECT ae.id as event_id, 
                   COUNT(ua.id) as user_alert_count
            FROM alert_events ae
            LEFT JOIN user_alerts ua ON ae.id = ua.event_id
            WHERE ae.entity_id = 93 AND ae.event_type = 'negative_comment'
            GROUP BY ae.id
            ORDER BY ae.id DESC
            LIMIT 10
        """)
        events_with_alerts = cur.fetchall()
        
        print(f"\n  Event distribution status (last 10 events):")
        for row in events_with_alerts:
            status = "✅ Distributed" if row['user_alert_count'] > 0 else "❌ NOT Distributed"
            print(f"    Event {row['event_id']}: {row['user_alert_count']} user alerts - {status}")
    
    print("\n" + "=" * 80)
    print("CHECKING RULE MATCHING LOGIC")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get the rule details
        cur.execute("""
            SELECT id, user_id, event_type, is_active, entity_scope
            FROM alert_rules
            WHERE id = 2
        """)
        rule = cur.fetchone()
        
        print(f"\n  Rule 2 details:")
        print(f"    User ID: {rule['user_id']}")
        print(f"    Event Type: {rule['event_type']}")
        print(f"    Is Active: {rule['is_active']}")
        print(f"    Entity Scope: {rule['entity_scope']}")
        
        # Check how the repository would match this rule
        entity_ids = rule['entity_scope'].get('entity_ids', []) if rule['entity_scope'] else []
        print(f"\n  Entity IDs in scope: {entity_ids}")
        
        if 93 in entity_ids:
            print("  ✅ Entity 93 IS in the rule's scope")
        else:
            print("  ❌ Entity 93 is NOT in the rule's scope")
    
    conn.close()
    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
