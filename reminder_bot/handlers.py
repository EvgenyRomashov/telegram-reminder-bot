"""
Bot command and message handlers.
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from sqlalchemy.exc import IntegrityError
from datetime import datetime, time
import pytz

from reminder_bot.database import get_db, User, Contact
from reminder_bot.reminders import generate_reminders_text

# Conversation states
(
    # Add conversation
    GET_NAME, GET_BIRTHDATE, GET_GROUP,
    # Delete conversation
    SELECT_CONTACT_TO_DELETE,
    # Settings conversation
    SELECT_SETTING, GET_NEW_TIME, GET_NEW_TIMEZONE
) = range(7)

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
        "<b>/settings</b> - Настроить время и часовой пояс уведомлений.\n"
        "<b>/test</b> - Получить тестовое уведомление прямо сейчас.\n\n"
        "Чтобы прервать любой диалог, в любой момент отправь /cancel."
    )
    await update.message.reply_html(help_text)

# --- Add Contact Conversation ---
async def add_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Начинаем добавлять новый контакт.\nПожалуйста, введи фамилию и имя. Чтобы отменить, введи /cancel.")
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text(f"Отлично, {context.user_data['full_name']}!\nТеперь введи дату рождения в формате <b>ДД.ММ.ГГГГ</b>.", parse_mode='HTML')
    return GET_BIRTHDATE

async def get_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        birth_date = datetime.strptime(update.message.text, "%d.%m.%Y").date()
        context.user_data['birth_date'] = birth_date
        await update.message.reply_text("Дата принята. Теперь выбери группу для этого контакта.", reply_markup=ReplyKeyboardMarkup([CONTACT_GROUPS], one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Выбери группу"))
        return GET_GROUP
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Пожалуйста, введи дату в формате <b>ДД.ММ.ГГГГ</b>.", parse_mode='HTML')
        return GET_BIRTHDATE

async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group = update.message.text
    if group not in CONTACT_GROUPS:
        await update.message.reply_text("Пожалуйста, выбери одну из предложенных групп с помощью кнопок.")
        return GET_GROUP
    context.user_data['group'] = group
    with get_db() as db:
        new_contact = Contact(user_id=update.effective_user.id, full_name=context.user_data['full_name'], birth_date=context.user_data['birth_date'], contact_group=context.user_data['group'])
        db.add(new_contact)
        db.commit()
    await update.message.reply_text(f"Отлично! Контакт {context.user_data['full_name']} успешно добавлен.\n\nЧтобы добавить еще один, снова отправь /add.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

# --- Delete Contact Conversation ---
async def delete_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    with get_db() as db:
        contacts = db.query(Contact).filter(Contact.user_id == user_id).all()
    if not contacts:
        await update.message.reply_text("У вас нет контактов для удаления.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    keyboard = [[contact.full_name] for contact in contacts]
    await update.message.reply_text("Выберите контакт, который хотите удалить. Чтобы отменить, нажмите /cancel.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Выберите контакт для удаления"))
    return SELECT_CONTACT_TO_DELETE

async def delete_contact_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact_name_to_delete = update.message.text
    user_id = update.effective_user.id
    with get_db() as db:
        contact = db.query(Contact).filter(Contact.user_id == user_id, Contact.full_name == contact_name_to_delete).first()
        if contact:
            db.delete(contact)
            db.commit()
            await update.message.reply_text(f"Контакт '{contact_name_to_delete}' был успешно удален.", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("Не удалось найти такой контакт. Попробуйте снова, вызвав /delete.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Settings Conversation ---
async def settings_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == user_id).one()
        current_time = user.notification_time.strftime('%H:%M')
        current_tz = user.timezone
    
    keyboard = [["Изменить время"], ["Изменить часовой пояс"]]
    await update.message.reply_text(
        f"Текущие настройки:\n"
        f"- Время уведомлений: <b>{current_time}</b>\n"
        f"- Часовой пояс: <b>{current_tz}</b>\n\n"
        "Что вы хотите изменить?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='HTML'
    )
    return SELECT_SETTING

async def settings_select_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "Изменить время":
        await update.message.reply_text("Пожалуйста, введите новый час для уведомлений (число от 0 до 23).", reply_markup=ReplyKeyboardRemove())
        return GET_NEW_TIME
    elif choice == "Изменить часовой пояс":
        await update.message.reply_text("Пожалуйста, введите ваш часовой пояс (например, Europe/Moscow, Asia/Yekaterinburg).", reply_markup=ReplyKeyboardRemove())
        return GET_NEW_TIMEZONE
    else:
        await update.message.reply_text("Пожалуйста, выберите один из вариантов на клавиатуре.")
        return SELECT_SETTING

async def set_notification_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_hour = int(update.message.text)
        if not (0 <= new_hour <= 23):
            raise ValueError()
        
        user_id = update.effective_user.id
        with get_db() as db:
            user = db.query(User).filter(User.telegram_id == user_id).one()
            user.notification_time = time(new_hour, 0)
            db.commit()
        
        await update.message.reply_text(f"Отлично! Время уведомлений изменено на {new_hour}:00.")
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Неверное значение. Пожалуйста, введите час в виде числа от 0 до 23.")
        return GET_NEW_TIME

async def set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_tz_str = update.message.text
        # Validate timezone
        pytz.timezone(new_tz_str)
        
        user_id = update.effective_user.id
        with get_db() as db:
            user = db.query(User).filter(User.telegram_id == user_id).one()
            user.timezone = new_tz_str
            db.commit()

        await update.message.reply_text(f"Отлично! Ваш часовой пояс изменен на {new_tz_str}.")
        return ConversationHandler.END
    except pytz.UnknownTimeZoneError:
        await update.message.reply_text("Не удалось распознать такой часовой пояс. Пожалуйста, попробуйте еще раз (например, Europe/Moscow).")
        return GET_NEW_TIMEZONE

# --- General Conversation Fallback ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends any conversation."""
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

# --- Standalone Commands ---
async def test_notification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message_text = generate_reminders_text(user_id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, parse_mode='HTML')

async def list_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message_text = generate_reminders_text(user_id)
    await update.message.reply_text(message_text, parse_mode='HTML')

# --- Handler Registration ---
def register_handlers(application: Application):
    """Registers all the handlers for the bot."""
    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_contact_start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthdate)],
            GET_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    delete_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_contact_start)],
        states={
            SELECT_CONTACT_TO_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_contact_selected)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    settings_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("settings", settings_start)],
        states={
            SELECT_SETTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_select_action)],
            GET_NEW_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_notification_time)],
            GET_NEW_TIMEZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_timezone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test_notification))
    application.add_handler(CommandHandler("list", list_contacts))
    application.add_handler(add_conv_handler)
    application.add_handler(delete_conv_handler)
    application.add_handler(settings_conv_handler)
