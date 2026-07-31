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
    SELECT_SETTING, GET_NEW_TIME, GET_NEW_TIMEZONE,
    # Edit conversation
    SELECT_CONTACT_TO_EDIT, SELECT_FIELD_TO_EDIT, GET_EDITED_VALUE
) = range(10)

# Predefined contact groups and edit choices
CONTACT_GROUPS = ["Семья", "Друзья", "Коллеги", "Знакомые", "Важное"]
EDIT_CHOICES = ["Имя", "Дату", "Группу"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued and registers the user."""
    telegram_user = update.effective_user
    if not telegram_user:
        return
    user_id = telegram_user.id
    first_name = telegram_user.first_name
    username = telegram_user.username
    with get_db() as db:
        if not db.query(User).filter(User.telegram_id == user_id).first():
            db.add(User(telegram_id=user_id, first_name=first_name, username=username))
            db.commit()
            await update.message.reply_text(
                f"Привет, {first_name}! Я бот-напоминалка. Используй /help, чтобы увидеть, что я умею."
            )
        else:
            await update.message.reply_text(f"С возвращением, {first_name}! Используй /help для просмотра команд.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    help_text = (
        "<b>Основные команды:</b>\n"
        "/add - Добавить день рождения\n"
        "/list - Показать все дни рождения\n"
        "/edit - Редактировать контакт\n"
        "/delete - Удалить контакт\n"
        "/settings - Настроить уведомления\n"
        "/test - Прислать тестовое уведомление\n"
        "/cancel - Отменить текущее действие"
    )
    await update.message.reply_html(help_text)

# --- Add Contact Conversation ---
async def add_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите фамилию и имя. Для отмены введите /cancel.")
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text(f"Отлично! Теперь введите дату рождения для '{context.user_data['full_name']}' в формате ДД.ММ.ГГГГ.")
    return GET_BIRTHDATE

async def get_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['birth_date'] = datetime.strptime(update.message.text, "%d.%m.%Y").date()
        await update.message.reply_text("Выберите группу.", reply_markup=ReplyKeyboardMarkup([CONTACT_GROUPS], one_time_keyboard=True))
        return GET_GROUP
    except ValueError:
        await update.message.reply_text("Неверный формат. Введите дату как ДД.ММ.ГГГГ.")
        return GET_BIRTHDATE

async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['group'] = update.message.text
    with get_db() as db:
        db.add(Contact(**context.user_data, user_id=update.effective_user.id))
        db.commit()
    await update.message.reply_text(f"Контакт {context.user_data['full_name']} успешно добавлен! Для добавления еще одного, введите /add.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

# --- Delete Contact Conversation ---
async def delete_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with get_db() as db:
        contacts = db.query(Contact).filter(Contact.user_id == update.effective_user.id).all()
    if not contacts:
        await update.message.reply_text("У вас нет контактов для удаления.")
        return ConversationHandler.END
    keyboard = [[c.full_name] for c in contacts]
    await update.message.reply_text("Выберите контакт для удаления.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return SELECT_CONTACT_TO_DELETE

async def delete_contact_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with get_db() as db:
        contact = db.query(Contact).filter(Contact.user_id == update.effective_user.id, Contact.full_name == update.message.text).first()
        if contact:
            db.delete(contact)
            db.commit()
            await update.message.reply_text(f"Контакт '{update.message.text}' удален.", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("Контакт не найден.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Edit Contact Conversation ---
async def edit_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with get_db() as db:
        contacts = db.query(Contact).filter(Contact.user_id == update.effective_user.id).all()
    if not contacts:
        await update.message.reply_text("У вас нет контактов для редактирования.")
        return ConversationHandler.END
    keyboard = [[c.full_name] for c in contacts]
    await update.message.reply_text("Выберите контакт для редактирования.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return SELECT_CONTACT_TO_EDIT

async def edit_select_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact_name = update.message.text
    with get_db() as db:
        contact = db.query(Contact).filter(Contact.user_id == update.effective_user.id, Contact.full_name == contact_name).first()
    if not contact:
        await update.message.reply_text("Контакт не найден.")
        return ConversationHandler.END
    context.user_data['contact_id_to_edit'] = contact.id
    await update.message.reply_text("Что именно вы хотите изменить?", reply_markup=ReplyKeyboardMarkup([EDIT_CHOICES], one_time_keyboard=True))
    return SELECT_FIELD_TO_EDIT

async def edit_select_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    context.user_data['edit_choice'] = choice
    if choice == "Имя":
        await update.message.reply_text("Введите новое имя.", reply_markup=ReplyKeyboardRemove())
    elif choice == "Дату":
        await update.message.reply_text("Введите новую дату в формате ДД.ММ.ГГГГ.", reply_markup=ReplyKeyboardRemove())
    elif choice == "Группу":
        await update.message.reply_text("Выберите новую группу.", reply_markup=ReplyKeyboardMarkup([CONTACT_GROUPS], one_time_keyboard=True))
    else:
        await update.message.reply_text("Неверный выбор.")
        return ConversationHandler.END
    return GET_EDITED_VALUE

async def get_edited_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = context.user_data.get('edit_choice')
    contact_id = context.user_data.get('contact_id_to_edit')
    with get_db() as db:
        contact = db.query(Contact).filter(Contact.id == contact_id).one()
        if choice == "Имя":
            contact.full_name = update.message.text
            msg = "Имя изменено."
        elif choice == "Дату":
            try:
                contact.birth_date = datetime.strptime(update.message.text, "%d.%m.%Y").date()
                msg = "Дата рождения изменена."
            except ValueError:
                msg = "Неверный формат даты. Редактирование отменено."
        elif choice == "Группу":
            contact.contact_group = update.message.text
            msg = "Группа изменена."
        db.commit()
    await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

# --- Settings Conversation ---
async def settings_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == update.effective_user.id).one()
    await update.message.reply_text(
        f"Текущие настройки:\n- Время уведомлений: {user.notification_time.strftime('%H:%M')}\n- Часовой пояс: {user.timezone}\nЧто изменить?",
        reply_markup=ReplyKeyboardMarkup([["Изменить время"], ["Изменить часовой пояс"]], one_time_keyboard=True)
    )
    return SELECT_SETTING

async def settings_select_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if "время" in update.message.text.lower():
        await update.message.reply_text("Введите новый час (0-23).", reply_markup=ReplyKeyboardRemove())
        return GET_NEW_TIME
    elif "пояс" in update.message.text.lower():
        await update.message.reply_text("Введите часовой пояс (например, Europe/Moscow).", reply_markup=ReplyKeyboardRemove())
        return GET_NEW_TIMEZONE
    return SELECT_SETTING

async def set_notification_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_hour = int(update.message.text)
        if not 0 <= new_hour <= 23: raise ValueError
        with get_db() as db:
            user = db.query(User).filter(User.telegram_id == update.effective_user.id).one()
            user.notification_time = time(new_hour, 0)
            db.commit()
        await update.message.reply_text(f"Время уведомлений изменено на {new_hour}:00.")
        return ConversationHandler.END
    except (ValueError, TypeError):
        await update.message.reply_text("Введите час от 0 до 23.")
        return GET_NEW_TIME

async def set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        pytz.timezone(update.message.text)
        with get_db() as db:
            user = db.query(User).filter(User.telegram_id == update.effective_user.id).one()
            user.timezone = update.message.text
            db.commit()
        await update.message.reply_text(f"Часовой пояс изменен на {update.message.text}.")
        return ConversationHandler.END
    except pytz.UnknownTimeZoneError:
        await update.message.reply_text("Неизвестный часовой пояс. Попробуйте еще раз.")
        return GET_NEW_TIMEZONE

# --- General ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

async def test_notification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = generate_reminders_text(update.effective_user.id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, parse_mode='HTML')

async def list_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = generate_reminders_text(update.effective_user.id)
    await update.message.reply_text(message_text, parse_mode='HTML')

# --- Handler Registration ---
def register_handlers(application: Application):
    """Registers all handlers for the bot."""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test_notification))
    application.add_handler(CommandHandler("list", list_contacts))

    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", add_contact_start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthdate)],
            GET_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group)],
        }, fallbacks=[CommandHandler("cancel", cancel)]
    ))
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("delete", delete_contact_start)],
        states={SELECT_CONTACT_TO_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_contact_selected)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("settings", settings_start)],
        states={
            SELECT_SETTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_select_action)],
            GET_NEW_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_notification_time)],
            GET_NEW_TIMEZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_timezone)],
        }, fallbacks=[CommandHandler("cancel", cancel)]
    ))
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("edit", edit_contact_start)],
        states={
            SELECT_CONTACT_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_select_contact)],
            SELECT_FIELD_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_select_field)],
            GET_EDITED_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_edited_value)],
        }, fallbacks=[CommandHandler("cancel", cancel)]
    ))
