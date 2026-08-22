from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import Application, ConversationHandler, MessageHandler

from reminder_bot.handlers import (
    CANCEL_BTN,
    CANCEL_KEYBOARD,
    get_group,
    open_web_app,
    show_main_menu,
    register_handlers,
)


def test_cancel_button_is_visible():
    assert CANCEL_KEYBOARD.keyboard[0][0].text == CANCEL_BTN


def test_every_conversation_handles_cancel_button():
    application = Application.builder().token("123456:TEST_TOKEN").build()
    register_handlers(application)
    conversations = [
        handler
        for handlers in application.handlers.values()
        for handler in handlers
        if isinstance(handler, ConversationHandler)
    ]
    assert len(conversations) == 4
    assert all(
        any(isinstance(handler, MessageHandler) for handler in conversation.fallbacks)
        for conversation in conversations
    )


@pytest.mark.asyncio
async def test_get_group_saves_contact_and_restores_main_menu(monkeypatch):
    session = MagicMock()
    db_context = MagicMock()
    db_context.__enter__.return_value = session
    monkeypatch.setattr("reminder_bot.handlers.get_db", lambda: db_context)

    message = SimpleNamespace(text="Семья", reply_text=AsyncMock())
    update = SimpleNamespace(
        message=message, effective_user=SimpleNamespace(id=42)
    )
    context = SimpleNamespace(
        user_data={"full_name": "Иван Иванов", "birth_date": date(1990, 1, 2)}
    )

    result = await get_group(update, context)

    contact = session.add.call_args.args[0]
    assert contact.full_name == "Иван Иванов"
    assert contact.contact_group == "Семья"
    assert contact.user_id == 42
    session.commit.assert_called_once_with()
    assert context.user_data == {}
    assert result == ConversationHandler.END
    reply_markup = message.reply_text.await_args.kwargs["reply_markup"]
    assert reply_markup.keyboard[0][0].text == "➕ Добавить"


@pytest.mark.asyncio
async def test_show_main_menu_replaces_stale_keyboard():
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)

    await show_main_menu(update, SimpleNamespace())

    reply_markup = message.reply_text.await_args.kwargs["reply_markup"]
    assert reply_markup.keyboard[0][0].text == "➕ Добавить"
    assert "восстановлено" in message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_open_web_app_uses_authorized_inline_button(monkeypatch):
    monkeypatch.setattr("reminder_bot.handlers.WEB_APP_URL", "https://reminder.example")
    monkeypatch.setenv("BOT_TOKEN", "123:test-token")
    message = SimpleNamespace(reply_text=AsyncMock())
    await open_web_app(SimpleNamespace(message=message, effective_user=SimpleNamespace(id=42)), SimpleNamespace())
    markup = message.reply_text.await_args.kwargs["reply_markup"]
    button = markup.inline_keyboard[0][0]
    assert button.web_app.url.startswith("https://reminder.example#launch_token=")
