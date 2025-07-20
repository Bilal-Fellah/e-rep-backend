import requests

def schedule_jobs():
    from api.__init__ import scheduler

    @scheduler.task('cron', id='daily_route_caller', hour=6, minute=47)
    def scheduled_task():
        try:
            # Assuming app runs locally on port 5000
            response = requests.post("http://localhost:5000/api/facebook/get_all_followers_and_likes")
            print("✅ Scheduled job executed. Status code:", response.status_code)
        except Exception as e:
            print("❌ Scheduled job failed:", e)
