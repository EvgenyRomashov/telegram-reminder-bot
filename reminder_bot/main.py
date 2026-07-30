"""
Main entry point for the Telegram bot.
"""
import logging
from telegram.ext import Application
from dotenv import load_dotenv
import os

from reminder_bot.handlers import register_handlers
from reminder_bot.scheduler import start_scheduler
from reminder_bot.database import engine, Base

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

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(token).build()

    # Register all handlers
    register_handlers(application)

    # Start the scheduler
    start_scheduler(application.bot)

    logger.info("Bot started and listening for messages...")

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
