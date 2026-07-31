import pytest
from datetime import date
from freezegun import freeze_time

from reminder_bot.reminders import format_plural, generate_reminders_text
from reminder_bot.database import Base, User, Contact
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- Fixtures for testing ---

@pytest.fixture(scope="function")
def db_session():
    """
    Creates a new in-memory database session for each test function.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

# --- Tests for format_plural ---

plural_test_cases = [
    (1, "год"), (2, "года"), (3, "года"), (4, "года"), (5, "лет"),
    (21, "год"), (22, "года"), (25, "лет"),
]

@pytest.mark.parametrize("value, expected", plural_test_cases)
def test_format_plural_years(value, expected):
    """Tests the plural formatting for 'год'."""
    forms = ('год', 'года', 'лет')
    assert format_plural(value, forms) == expected

# --- Tests for generate_reminders_text ---

@freeze_time("2026-10-25")
def test_generate_reminders_text_with_contacts(db_session, mocker):
    """
    Tests the main text generation logic with a fixed date and mocked DB.
    """
    # Mock the get_db function to use our in-memory db_session
    mocker.patch("reminder_bot.reminders.get_db", return_value=db_session)

    # Setup test data
    test_user = User(telegram_id=123, first_name="Тест")
    
    # Contact 1: Birthday is today
    contact1 = Contact(user_id=123, full_name="Именинник Сегодня", birth_date=date(1990, 10, 25))
    
    # Contact 2: Birthday is tomorrow
    contact2 = Contact(user_id=123, full_name="Именинник Завтра", birth_date=date(2000, 10, 26))

    # Contact 3: Birthday in 10 days
    contact3 = Contact(user_id=123, full_name="Далекий Именинник", birth_date=date(1985, 11, 4))
    
    # Contact 4: Birthday already passed this year
    contact4 = Contact(user_id=123, full_name="Прошедший Именинник", birth_date=date(1995, 1, 15))

    db_session.add_all([test_user, contact1, contact2, contact3, contact4])
    db_session.commit()

    # Call the function under test
    result_text = generate_reminders_text(user_id=123)
    
    # Assertions
    assert "🎉 Напоминания о днях рождения:" in result_text
    # Check that contacts are ordered by days_until
    assert result_text.find("Сегодня") < result_text.find("Завтра") < result_text.find("Далекий") < result_text.find("Прошедший")

    # Check content for each contact
    assert "| Именинник Сегодня | день рождения сегодня! | 36 лет | 25 октября 1990 года |" in result_text
    assert "| Именинник Завтра | день рождения завтра! | 26 лет | 26 октября 2000 года |" in result_text
    assert "| Далекий Именинник | день рождения через 10 дней | 41 год | 4 ноября 1985 года |" in result_text
    assert "| Прошедший Именинник | день рождения через 82 дня | 32 года | 15 января 1995 года |" in result_text


def test_generate_reminders_text_no_contacts(db_session, mocker):
    """Tests the output when a user has no contacts."""
    mocker.patch("reminder_bot.reminders.get_db", return_value=db_session)
    
    test_user = User(telegram_id=456, first_name="Тест2")
    db_session.add(test_user)
    db_session.commit()

    result_text = generate_reminders_text(user_id=456)

    assert result_text == "У вас пока нет добавленных контактов. Используйте /add, чтобы добавить первый."

