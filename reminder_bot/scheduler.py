"""
Scheduler for sending daily birthday reminders.
"""
import logging
import pytz
from datetime import datetime
from telegram.ext import Application

from .database import get_db, User
from .reminders import generate_reminders_text

logger = logging.getLogger(__name__)

async def send_daily_reminders(bot: Application.bot):
    """
    This function is called by the scheduler.
    It checks for users who need a reminder at the current hour.
    """
    logger.info("Scheduler job started: Checking for users to notify.")
    now_utc = datetime.utcnow()
    
    with get_db() as db:
        users = db.query(User).filter(User.notifications_enabled == True).all()

    if not users:
        logger.info("No users with notifications enabled. Job finished.")
        return

    for user in users:
        try:
            user_tz = pytz.timezone(user.timezone)
            now_local = now_utc.astimezone(user_tz)
            
            # Check if the current local hour matches the user's preferred notification hour
            if now_local.hour == user.notification_time.hour:
                logger.info(f"Condition met for user {user.telegram_id}. Generating message.")
                message_text = generate_reminders_text(user.telegram_id)
                
                # Avoid sending empty/default messages
                if "У вас пока нет" not in message_text:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        parse_mode='HTML'
                    )
                    logger.info(f"Notification sent to user {user.telegram_id}.")
        except Exception as e:
            logger.error(f"Error processing user {user.telegram_id}: {e}", exc_info=True)
    
    logger.info("Scheduler job finished.")

