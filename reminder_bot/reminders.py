"""
Core logic for generating reminder messages.
"""
from datetime import date, datetime
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
        next_birthday = contact.birth_date.replace(year=today.year)
        if next_birthday < today:
            next_birthday = next_birthday.replace(year=today.year + 1)
        
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
            "text": f"| {contact.full_name} | день рождения {days_str} | {age} {format_plural(age, ('год', 'года', 'лет'))} | {birth_date_str} |"
        })

    # Sort reminders by days until birthday
    reminders.sort(key=lambda x: x['days_until'])
    
    header = "🎉 Напоминания о днях рождения:\n\n"
    return header + "\n".join([r['text'] for r in reminders])
