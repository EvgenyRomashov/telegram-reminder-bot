"""
Scheduler for sending daily birthday reminders.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def start_scheduler(bot):
    """Initializes and starts the scheduler."""
    scheduler = AsyncIOScheduler(timezone="UTC")

    # This job will run hourly to check for notifications to send
    scheduler.add_job(send_daily_reminders, "cron", hour="*", args=[bot])
    
    scheduler.start()

async def send_daily_reminders(bot):
    """
    This function is called by the scheduler.
    It checks for users who need a reminder at the current hour.
    """
    # Implementation will be added here
    print("Scheduler is running...") # Placeholder
