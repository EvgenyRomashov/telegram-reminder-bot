from telegram.ext import Application, ConversationHandler, MessageHandler

from reminder_bot.handlers import (
    CANCEL_BTN,
    CANCEL_KEYBOARD,
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
