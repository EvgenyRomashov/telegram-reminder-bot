"""
Main entry point for the Telegram bot.
"""
import logging
from telegram.ext import Application
from dotenv import load_dotenv
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from reminder_bot.scheduler import send_daily_reminders
from reminder_bot.handlers import register_handlers
from reminder_bot.database import engine, Base

async def post_init(application: Application) -> None:
    """
    Post-initialization function to set up the scheduler.
    This is called by the Application object after initialization but before polling starts.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(send_daily_reminders, "cron", minute="*", args=[application.bot])
    scheduler.start()

def main() -> None:
    """Start the telegram bot."""
    # Load environment variables from .env file
    load_dotenv()

    # Set up logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    logger = logging.getLogger(__name__)

    # Get the bot token from environment variables
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN environment variable not set!")
        return

    # Create the database tables
    Base.metadata.create_all(bind=engine)

    # Create the Application and pass it your bot's token, with post_init hook.
    application = Application.builder().token(token).post_init(post_init).build()

    # Register all handlers
    register_handlers(application)

    logger.info("Bot started and listening for messages...")

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
