"""
Core logic for generating reminder messages.
"""
from datetime import date
from html import escape
from .database import get_db, Contact

def get_russian_month(month_number: int) -> str:
    """Returns the month name in Russian genitive case."""
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    return months[month_number - 1]

def format_plural(value: int, forms: tuple[str, str, str]) -> str:
    """Chooses the correct plural form for a given value."""
    if value % 10 == 1 and value % 100 != 11:
        return forms[0]
    elif 2 <= value % 10 <= 4 and (value % 100 < 10 or value % 100 >= 20):
        return forms[1]
    else:
        return forms[2]

TELEGRAM_MESSAGE_LIMIT = 4096

def split_telegram_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split text on line boundaries into messages accepted by Telegram."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                chunks.append(current.rstrip("\n"))
                current = ""
            chunks.extend(line[i:i + limit] for i in range(0, len(line), limit))
        elif len(current) + len(line) > limit:
            chunks.append(current.rstrip("\n"))
            current = line
        else:
            current += line
    if current:
        chunks.append(current.rstrip("\n"))
    return chunks or [""]

def next_birthday_for(birth_date: date, today: date) -> date:
    """Return the next birthday; 29 February is observed on 28 February."""
    day = 28 if birth_date.month == 2 and birth_date.day == 29 else birth_date.day
    candidate = date(today.year, birth_date.month, day)
    if candidate < today:
        candidate = date(today.year + 1, birth_date.month, day)
    return candidate

def generate_reminders_text(user_id: int) -> str:
    """
    Generates the text for a user's birthday reminders.
    """
    today = date.today()
    reminders = []
    
    with get_db() as db:
        contacts = db.query(Contact).filter(Contact.user_id == user_id).all()

    if not contacts:
        return "У вас пока нет добавленных контактов. Используйте /add, чтобы добавить первый."

    for contact in contacts:
        # Calculate next birthday
        next_birthday = next_birthday_for(contact.birth_date, today)
        
        # Calculate days until next birthday
        days_until = (next_birthday - today).days
        
        # Calculate age
        age = next_birthday.year - contact.birth_date.year
        
        # Format birth date string
        birth_date_str = f"{contact.birth_date.day} {get_russian_month(contact.birth_date.month)} {contact.birth_date.year} года"
        
        # Format days_until string
        if days_until == 0:
            days_str = "сегодня!"
        elif days_until == 1:
            days_str = "завтра!"
        else:
            days_forms = ("день", "дня", "дней")
            days_str = f"через {days_until} {format_plural(days_until, days_forms)}"

        reminders.append({
            "days_until": days_until,
            "text": f"| {escape(contact.full_name)} | день рождения {days_str} | {age} {format_plural(age, ('год', 'года', 'лет'))} | {birth_date_str} |"
        })

    # Sort reminders by days until birthday
    reminders.sort(key=lambda x: x['days_until'])
    
    header = "🎉 Напоминания о днях рождения:\n\n"
    return header + "\n".join([r['text'] for r in reminders])
