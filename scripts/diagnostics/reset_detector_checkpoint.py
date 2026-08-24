"""Reset the negative_comment detector checkpoint to reprocess comments"""
import psycopg2
from datetime import datetime, timedelta

def main():
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        user="bilal",
        password="chupakabra",
        database="erep-db"
    )
    
    print("=" * 80)
    print("RESETTING NEGATIVE_COMMENT DETECTOR CHECKPOINT")
    print("=" * 80)
    
    with conn.cursor() as cur:
        # Get current checkpoint
        cur.execute("""
            SELECT cursor_ts, updated_at
            FROM alert_detector_checkpoints
            WHERE detector_name = 'negative_comment'
        """)
        current = cur.fetchone()
        
        if current:
            print(f"\nCurrent checkpoint:")
            print(f"  Cursor: {current[0]}")
            print(f"  Updated: {current[1]}")
        else:
            print("\nNo checkpoint found")
        
        # Option 1: Set to a date before the comments (e.g., 10 days ago)
        new_cursor = datetime.utcnow() - timedelta(days=10)
        
        print(f"\n⚠️  This will reset the checkpoint to: {new_cursor}")
        print(f"   This will cause the detector to reprocess ALL comments")
        print(f"   labeled after this date, including old ones.\n")
        
        response = input("Do you want to proceed? (yes/no): ")
        
        if response.lower() != 'yes':
            print("\nAborted. No changes made.")
            conn.close()
            return
        
        # Update the checkpoint
        cur.execute("""
            UPDATE alert_detector_checkpoints
            SET cursor_ts = %s, updated_at = %s
            WHERE detector_name = 'negative_comment'
        """, (new_cursor, datetime.utcnow()))
        
        conn.commit()
        
        print(f"\n✅ Checkpoint updated!")
        print(f"\nNow run the alerts engine again:")
        print(f"  POST /api/alerts/engine/run")
        print(f"\nThe detector will reprocess comments and create user alerts for your rule.")
    
    conn.close()

if __name__ == "__main__":
    main()
