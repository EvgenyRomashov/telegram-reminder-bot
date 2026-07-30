"""
Bot command and message handlers.
"""
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from sqlalchemy.exc import IntegrityError
import datetime

from reminder_bot.database import get_db, User

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued and registers the user."""
    telegram_user = update.effective_user
    if not telegram_user:
        return

    user_id = telegram_user.id
    first_name = telegram_user.first_name
    username = telegram_user.username

    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == user_id).first()

        if user is None:
            # Register new user
            new_user = User(
                telegram_id=user_id,
                first_name=first_name,
                username=username,
                # Default notification time set in model
                # Default timezone set in model
            )
            db.add(new_user)
            try:
                db.commit()
                db.refresh(new_user)
                welcome_message = (
                    f"Привет, {first_name}! Я бот-напоминалка о днях рождения. "
                    "Я помогу тебе не забыть о важных датах."
                    "\n\nИспользуй команду /add, чтобы добавить день рождения. "
                    "Команда /help покажет все доступные команды."
                    "\n\nПо умолчанию напоминания приходят в 09:00 по московскому времени. "
                    "Ты можешь настроить это с помощью команды /settings."
                )
                await update.message.reply_text(welcome_message)
            except IntegrityError:
                db.rollback()
                await update.message.reply_text("Произошла ошибка при регистрации. Пожалуйста, попробуй еще раз.")
        else:
            # User already exists
            welcome_back_message = (
                f"С возвращением, {first_name}! Я готов продолжать помогать тебе."
                "\n\nИспользуй /help для просмотра команд."
            )
            await update.message.reply_text(welcome_back_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    help_text = (
        "Вот список команд, которые я понимаю:\n\n"
        "<b>/start</b> - Начать работу с ботом и зарегистрироваться.\n"
        "<b>/help</b> - Показать это справочное сообщение.\n"
        "<b>/add</b> - Добавить новый день рождения (будет запрошено ФИО, дата, группа).\n"
        "<b>/list</b> - Показать все дни рождения, которые ты добавил.\n"
        "<b>/delete</b> - Удалить день рождения из списка.\n"
        "<b>/settings</b> - Настроить время, в которое ты будешь получать ежедневные напоминания, и указать свой часовой пояс.\n\n"
        "Я буду отправлять тебе ежедневные напоминания со списком всех людей, у кого скоро день рождения, указывая, сколько дней осталось, сколько лет исполнится, и полную дату рождения."
    )
    await update.message.reply_html(help_text)

def register_handlers(application: Application):
    """Registers all the handlers for the bot."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    # More handlers will be added here
