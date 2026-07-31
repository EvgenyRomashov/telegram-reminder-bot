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
    SELECT_CONTACT_TO_EDIT, SELECT_FIELD_TO_EDIT, GET_EDITED_VALUE,
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
        "<b>/edit</b> - Редактировать существующий контакт.\n"
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

# --- Edit Contact Conversation ---
async def edit_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    with get_db() as db:
        contacts = db.query(Contact).filter(Contact.user_id == user_id).all()
    if not contacts:
        await update.message.reply_text("У вас нет контактов для редактирования.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    keyboard = [[contact.full_name] for contact in contacts]
    await update.message.reply_text("Выберите контакт для редактирования.", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
    return SELECT_CONTACT_TO_EDIT

async def edit_select_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact_name = update.message.text
    user_id = update.effective_user.id
    with get_db() as db:
        contact = db.query(Contact).filter(Contact.user_id == user_id, Contact.full_name == contact_name).first()
    if not contact:
        await update.message.reply_text("Контакт не найден. Попробуйте снова.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    context.user_data['contact_id_to_edit'] = contact.id
    keyboard = [EDIT_CHOICES]
    await update.message.reply_text("Что именно вы хотите изменить?", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))
    return SELECT_FIELD_TO_EDIT

async def edit_select_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    context.user_data['edit_choice'] = choice
    
    if choice == "Имя":
        await update.message.reply_text("Введите новое имя.", reply_markup=ReplyKeyboardRemove())
    elif choice == "Дату":
        await update.message.reply_text("Введите новую дату в формате ДД.ММ.ГГГГ.", reply_markup=ReplyKeyboardRemove())
    elif choice == "Группу":
        await update.message.reply_text("Выберите новую группу.", reply_markup=ReplyKeyboardMarkup([CONTACT_GROUPS], one_time_keyboard=True, resize_keyboard=True))
    else:
        await update.message.reply_text("Неверный выбор. Пожалуйста, начните сначала /edit.")
        return ConversationHandler.END
        
    return GET_EDITED_VALUE

async def get_edited_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = context.user_data.get('edit_choice')
    contact_id = context.user_data.get('contact_id_to_edit')
    
    with get_db() as db:
        contact = db.query(Contact).filter(Contact.id == contact_id).one()
        
        if choice == "Имя":
            contact.full_name = update.message.text
            await update.message.reply_text(f"Имя контакта изменено на {contact.full_name}.", reply_markup=ReplyKeyboardRemove())
        elif choice == "Дату":
            try:
                contact.birth_date = datetime.strptime(update.message.text, "%d.%m.%Y").date()
                await update.message.reply_text(f"Дата рождения изменена.", reply_markup=ReplyKeyboardRemove())
            except ValueError:
                await update.message.reply_text("Неверный формат даты. Попробуйте /edit снова.")
                return ConversationHandler.END
        elif choice == "Группу":
            new_group = update.message.text
            if new_group not in CONTACT_GROUPS:
                await update.message.reply_text("Пожалуйста, выберите группу из предложенных. Попробуйте /edit снова.")
                return ConversationHandler.END
            contact.contact_group = new_group
            await update.message.reply_text(f"Группа изменена на {new_group}.", reply_markup=ReplyKeyboardRemove())
            
        db.commit()

    context.user_data.clear()
    return ConversationHandler.END

# --- Settings Conversation ---
async def settings_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (existing settings_start function) ...
# ... (all other existing functions) ...

# --- Handler Registration ---
def register_handlers(application: Application):
    """Registers all the handlers for the bot."""
    # ... (existing add and delete handlers) ...

    edit_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("edit", edit_contact_start)],
        states={
            SELECT_CONTACT_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_select_contact)],
            SELECT_FIELD_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_select_field)],
            GET_EDITED_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_edited_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test_notification))
    application.add_handler(CommandHandler("list", list_contacts))
    application.add_handler(add_conv_handler)
    application.add_handler(delete_conv_handler)
    application.add_handler(edit_conv_handler)
