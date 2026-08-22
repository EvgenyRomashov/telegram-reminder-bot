"""
Main entry point for the Telegram bot.
"""
import logging
from telegram import MenuButtonWebApp, WebAppInfo
from telegram.ext import Application
from dotenv import load_dotenv
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from reminder_bot.scheduler import send_daily_reminders
from reminder_bot.handlers import register_handlers
from reminder_bot.database import engine, Base

async def post_shutdown(application: Application) -> None:
    scheduler = application.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)

async def error_handler(update: object, context) -> None:
    logging.getLogger(__name__).error("Unhandled update error", exc_info=context.error)

async def post_init(application: Application) -> None:
    """
    Post-initialization function to set up the scheduler.
    This is called by the Application object after initialization but before polling starts.
    """
    web_app_url = os.getenv("WEB_APP_URL", "").strip()
    if web_app_url.startswith("https://"):
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Дни рождения", web_app=WebAppInfo(web_app_url)
                )
            )
        except Exception:
            logging.getLogger(__name__).exception("Failed to configure Mini App menu button")

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        send_daily_reminders, "cron", hour="*", minute=0, args=[application.bot],
        id="daily-reminders", replace_existing=True, coalesce=True, max_instances=1,
        misfire_grace_time=1800,
    )
    application.bot_data["scheduler"] = scheduler
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
    application = Application.builder().token(token).post_init(post_init).post_shutdown(post_shutdown).build()

    # Register all handlers
    register_handlers(application)
    application.add_error_handler(error_handler)

    logger.info("Bot started and listening for messages...")

    # Run the bot until the user presses Ctrl-C
    application.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
