"""
Diagnostic script to check scraping status and failed pages.
"""
from datetime import datetime, time, timedelta
from api import create_app
from api.models.page_history_model import PageHistory
from api.models.page_model import Page
from api.repositories.page_history_repository import PageHistoryRepository
from sqlalchemy import select, and_
from api.models.comment_model import db


def check_day_records(date_to_check, label):
    """Check records for a specific day."""
    day_start = datetime.combine(date_to_check, time.min)
    day_end = datetime.combine(date_to_check, time.max)
    
    print(f"\n{'='*80}")
    print(f"{label} - {date_to_check}")
    print(f"{'='*80}\n")
    
    # Check total pages_history records for this day
    stmt = select(PageHistory).where(
        and_(
            PageHistory.recorded_at >= day_start,
            PageHistory.recorded_at <= day_end
        )
    )
    day_records = db.session.execute(stmt).scalars().all()
    
    print(f"Total pages_history records: {len(day_records)}")
    
    if not day_records:
        print(f"\n⚠️  NO PAGES_HISTORY RECORDS FOR {label.upper()}!")
        return 0, 0
    
    print(f"\n{'─'*80}")
    print("Analyzing pages_history records...")
    print(f"{'─'*80}\n")
    
    # Analyze each record
    failed_count = 0
    valid_count = 0
    
    for record in day_records:
        missing_keys = PageHistoryRepository.validate_data_structure(
            record.data,
            record.page.platform
        )
        
        if missing_keys:
            failed_count += 1
            print(f"❌ FAILED: {record.page.name} ({record.page.platform})")
            print(f"   Page ID: {record.page_id}")
            print(f"   Missing keys: {', '.join(missing_keys)}")
            print(f"   Recorded at: {record.recorded_at}")
            print(f"   Entity: {record.page.entity.name if record.page.entity else 'N/A'}")
            print(f"   Entity active (to_scrape): {record.page.entity.to_scrape if record.page.entity else 'N/A'}")
            print()
        else:
            valid_count += 1
    
    print(f"{'─'*80}")
    print(f"{label} Summary:")
    print(f"  Valid records: {valid_count}")
    print(f"  Failed records: {failed_count}")
    print(f"{'─'*80}\n")
    
    return valid_count, failed_count


def check_time_window_records():
    """Check records from yesterday 10pm until now."""
    now_utc = datetime.utcnow()
    yesterday_utc = now_utc.date() - timedelta(days=1)
    
    # Start from yesterday at 10pm (22:00)
    start_time = datetime.combine(yesterday_utc, time(22, 0, 0))
    end_time = now_utc
    
    print(f"\n{'='*80}")
    print(f"Active Time Window (Yesterday 10pm - Now)")
    print(f"{'='*80}")
    print(f"Start: {start_time}")
    print(f"End:   {end_time}")
    print(f"{'='*80}\n")
    
    # Check pages_history records in this window
    stmt = select(PageHistory).where(
        and_(
            PageHistory.recorded_at >= start_time,
            PageHistory.recorded_at <= end_time
        )
    )
    window_records = db.session.execute(stmt).scalars().all()
    
    print(f"Total pages_history records in window: {len(window_records)}")
    
    if not window_records:
        print(f"\n⚠️  NO PAGES_HISTORY RECORDS IN THIS TIME WINDOW!")
        return 0, 0
    
    print(f"\n{'─'*80}")
    print("Analyzing records in time window...")
    print(f"{'─'*80}\n")
    
    # Analyze each record
    failed_count = 0
    valid_count = 0
    
    for record in window_records:
        missing_keys = PageHistoryRepository.validate_data_structure(
            record.data,
            record.page.platform
        )
        
        if missing_keys:
            failed_count += 1
            print(f"❌ FAILED: {record.page.name} ({record.page.platform})")
            print(f"   Page ID: {record.page_id}")
            print(f"   Missing keys: {', '.join(missing_keys)}")
            print(f"   Recorded at: {record.recorded_at}")
            print(f"   Entity: {record.page.entity.name if record.page.entity else 'N/A'}")
            print(f"   Entity active (to_scrape): {record.page.entity.to_scrape if record.page.entity else 'N/A'}")
            print()
        else:
            valid_count += 1
    
    print(f"{'─'*80}")
    print(f"Time Window Summary:")
    print(f"  Valid records: {valid_count}")
    print(f"  Failed records: {failed_count}")
    print(f"{'─'*80}\n")
    
    return valid_count, failed_count


def check_scraping_status():
    """Check the current scraping status and identify issues."""
    app = create_app()
    
    with app.app_context():
        today_utc = datetime.utcnow().date()
        yesterday_utc = today_utc - timedelta(days=1)
        
        # Check yesterday (full day)
        yesterday_valid, yesterday_failed = check_day_records(yesterday_utc, "Yesterday (Full Day)")
        
        # Check today (full day)
        today_valid, today_failed = check_day_records(today_utc, "Today (Full Day)")
        
        # Check the actual time window used by the API (yesterday 10pm - now)
        window_valid, window_failed = check_time_window_records()
        
        # Overall summary
        print(f"\n{'='*80}")
        print("OVERALL SUMMARY")
        print(f"{'='*80}\n")
        print(f"Yesterday (full day): {yesterday_valid} valid, {yesterday_failed} failed")
        print(f"Today (full day):     {today_valid} valid, {today_failed} failed")
        print(f"")
        print(f"🎯 ACTIVE WINDOW (Yesterday 10pm - Now): {window_valid} valid, {window_failed} failed")
        print(f"   ↑ This is what the API endpoint will return")
        
        if window_failed == 0:
            print("\n✅ All pages_history records in the active window are valid (no missing data)!")
            print("This is why the apify endpoint returns empty results.")
        else:
            print(f"\n⚠️  {window_failed} failed records found in active window.")
            print("These should be returned by the apify endpoint.")
        
        print(f"\n{'='*80}")
        print("Testing get_failed_pages_for_today() API method...")
        print(f"{'='*80}\n")
        
        failed_pages = PageHistoryRepository.get_failed_pages_for_today()
        print(f"Failed pages returned by API: {len(failed_pages)}")
        
        if failed_pages:
            for fp in failed_pages:
                print(f"\n  Page ID: {fp['page_id']}")
                print(f"  Platform: {fp['platform']}")
                print(f"  Missing keys: {', '.join(fp['missing_keys'])}")
                print(f"  Recorded at: {fp['recorded_at']}")
        
        if len(failed_pages) != window_failed:
            print(f"\n⚠️  WARNING: API returned {len(failed_pages)} failed pages, but we found {window_failed} in the window!")
            print("This might indicate inactive entities are being filtered out.")


if __name__ == "__main__":
    check_scraping_status()
