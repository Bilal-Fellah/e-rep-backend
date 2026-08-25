"""Test rule matching logic"""
import psycopg2
from psycopg2.extras import RealDictCursor

def test_matching_sql():
    """Test the SQL query that matches rules"""
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        user="bilal",
        password="chupakabra",
        database="erep-db"
    )
    
    print("=" * 80)
    print("TESTING RULE MATCHING FOR ENTITY 93")
    print("=" * 80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # This mimics what list_matching_rules does
        cur.execute("""
            SELECT id, user_id, event_type, is_active, entity_scope
            FROM alert_rules
            WHERE is_active = TRUE AND event_type = 'negative_comment'
        """)
        rules = cur.fetchall()
        
        print(f"\n✅ Found {len(rules)} active negative_comment rule(s)")
        
        entity_id = 93
        matched = []
        
        for rule in rules:
            print(f"\n  Checking Rule {rule['id']}:")
            print(f"    User: {rule['user_id']}")
            print(f"    Entity Scope: {rule['entity_scope']}")
            
            scope = rule['entity_scope'] or {}
            ids = scope.get('entity_ids') if isinstance(scope, dict) else None
            
            print(f"    Entity IDs in scope: {ids}")
            
            if not ids:
                print(f"    ✅ MATCH: No entity scope (global rule)")
                matched.append(rule)
            elif entity_id in ids:
                print(f"    ✅ MATCH: Entity {entity_id} is in scope")
                matched.append(rule)
            else:
                print(f"    ❌ NO MATCH: Entity {entity_id} not in scope")
        
        print(f"\n{'=' * 80}")
        print(f"MATCHED RULES: {len(matched)}")
        print(f"{'=' * 80}")
        
        for rule in matched:
            print(f"\n  Rule {rule['id']} for User {rule['user_id']} SHOULD get alerts")
    
    conn.close()

if __name__ == "__main__":
    test_matching_sql()
