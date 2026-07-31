import pytest
from reminder_bot.reminders import format_plural

# Тест-кейсы для функции format_plural
# (значение, ожидаемый результат)
plural_test_cases = [
    (1, "год"), (2, "года"), (3, "года"), (4, "года"), (5, "лет"),
    (10, "лет"), (11, "лет"), (12, "лет"), (13, "лет"), (14, "лет"),
    (20, "лет"), (21, "год"), (22, "года"), (25, "лет"), (31, "год")
]

@pytest.mark.parametrize("value, expected", plural_test_cases)
def test_format_plural(value, expected):
    """Тестирует правильность выбора склонения для слова 'год'."""
    forms = ('год', 'года', 'лет')
    assert format_plural(value, forms) == expected

def test_format_plural_other_forms():
    """Тестирует другие формы слов."""
    day_forms = ('день', 'дня', 'дней')
    assert format_plural(1, day_forms) == 'день'
    assert format_plural(2, day_forms) == 'дня'
    assert format_plural(5, day_forms) == 'дней'
