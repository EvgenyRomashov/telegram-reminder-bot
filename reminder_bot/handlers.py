"""
Bot command and message handlers.
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from reminder_bot.database import get_db, User, Contact
from reminder_bot.reminders import generate_reminders_text

# Conversation states
GET_NAME, GET_BIRTHDATE, GET_GROUP = range(3)

# Predefined contact groups
CONTACT_GROUPS = ["Семья", "Друзья", "Коллеги", "Знакомые", "Важное"]


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
            new_user = User(
                telegram_id=user_id, first_name=first_name, username=username
            )
            db.add(new_user)
            try:
                db.commit()
                welcome_message = (
                    f"Привет, {first_name}! Я бот-напоминалка о днях рождения.\n\n"
                    "Используй /add, чтобы добавить день рождения, или /help для просмотра всех команд."
                )
                await update.message.reply_text(welcome_message)
            except IntegrityError:
                db.rollback()
                await update.message.reply_text("Произошла ошибка при регистрации. Пожалуйста, попробуй еще раз.")
        else:
            await update.message.reply_text(f"С возвращением, {first_name}! Используй /help для просмотра команд.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    help_text = (
        "Вот список команд, которые я понимаю:\n\n"
        "<b>/start</b> - Начать работу с ботом и зарегистрироваться.\n"
        "<b>/help</b> - Показать это справочное сообщение.\n"
        "<b>/add</b> - Добавить новый день рождения.\n"
        "<b>/list</b> - Показать все добавленные дни рождения.\n"
        "<b>/delete</b> - Удалить день рождения из списка.\n"
        "<b>/settings</b> - Настроить время уведомлений.\n"
        "<b>/test</b> - Получить тестовое уведомление прямо сейчас.\n\n"
        "Чтобы прервать добавление контакта, в любой момент отправь /cancel."
    )
    await update.message.reply_html(help_text)


async def add_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to add a new contact."""
    await update.message.reply_text(
        "Начинаем добавлять новый контакт.\n"
        "Пожалуйста, введи фамилию и имя. "
        "Чтобы отменить, введи /cancel."
    )
    return GET_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the name and asks for the birthdate."""
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text(
        f"Отлично, {context.user_data['full_name']}!\n"
        "Теперь введи дату рождения в формате <b>ДД.ММ.ГГГГ</b>.",
        parse_mode='HTML'
    )
    return GET_BIRTHDATE


async def get_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the birthdate and asks for the group."""
    try:
        birth_date = datetime.strptime(update.message.text, "%d.%m.%Y").date()
        context.user_data['birth_date'] = birth_date
        reply_keyboard = [CONTACT_GROUPS]
        await update.message.reply_text(
            "Дата принята. Теперь выбери группу для этого контакта.",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, resize_keyboard=True,
                input_field_placeholder="Выбери группу"
            ),
        )
        return GET_GROUP
    except ValueError:
        await update.message.reply_text(
            "Неверный формат даты. Пожалуйста, введи дату в формате <b>ДД.ММ.ГГГГ</b>.",
            parse_mode='HTML'
        )
        return GET_BIRTHDATE


async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the group, saves the contact to DB, and ends the conversation."""
    group = update.message.text
    if group not in CONTACT_GROUPS:
        await update.message.reply_text(
            "Пожалуйста, выбери одну из предложенных групп с помощью кнопок."
        )
        return GET_GROUP

    context.user_data['group'] = group
    user_id = update.effective_user.id

    with get_db() as db:
        new_contact = Contact(
            user_id=user_id,
            full_name=context.user_data['full_name'],
            birth_date=context.user_data['birth_date'],
            contact_group=context.user_data['group']
        )
        db.add(new_contact)
        db.commit()

    await update.message.reply_text(
        f"Отлично! Контакт {context.user_data['full_name']} успешно добавлен.\n\n"
        "Чтобы добавить еще один, снова отправь /add.",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "Добавление контакта отменено.", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


def register_handlers(application: Application):
    """Registers all the handlers for the bot."""

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_contact_start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthdate)],
            GET_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("test", test_notification))
    # More handlers will be added here

async def test_notification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates and sends a test notification for the user."""
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    message_text = generate_reminders_text(user_id)
    await update.message.reply_text(message_text, parse_mode='HTML')
