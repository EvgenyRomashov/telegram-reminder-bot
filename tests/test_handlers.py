from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import Application, ConversationHandler, MessageHandler

from reminder_bot.handlers import (
    CANCEL_BTN,
    CANCEL_KEYBOARD,
    get_group,
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
