"""Telegram Mini App authentication."""

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, status

MAX_AUTH_AGE_SECONDS = int(os.getenv("MINI_APP_AUTH_MAX_AGE", "86400"))
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str
    username: str | None = None

def _hmac_hash(values: dict[str, str], secret_key: bytes) -> str:
    data_check_string = "\\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    return hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

def validate_init_data(init_data: str, bot_token: str, now: int | None = None) -> TelegramUser:
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", None)
    if not received_hash:
        raise ValueError("Telegram hash is missing")

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    without_signature = {key: value for key, value in values.items() if key != "signature"}
    calculated_without = _hmac_hash(without_signature, secret_key)
    calculated_with = _hmac_hash(values, secret_key)

    valid_without = hmac.compare_digest(calculated_without, received_hash)
    valid_with = hmac.compare_digest(calculated_with, received_hash)
    if not valid_without and not valid_with:
        logger.warning(
            "Telegram initData HMAC mismatch: fields=%s auth_date=%s "
            "received=%s without_signature=%s with_signature=%s",
            sorted(values),
            values.get("auth_date"),
            received_hash[:12],
            calculated_without[:12],
            calculated_with[:12],
        )
        raise ValueError("Invalid Telegram signature")

    current_time = int(time.time()) if now is None else now
    try:
        auth_date = int(values["auth_date"])
    except (KeyError, ValueError) as exc:
        raise ValueError("Invalid Telegram auth_date") from exc
    if auth_date > current_time + 30 or current_time - auth_date > MAX_AUTH_AGE_SECONDS:
        raise ValueError("Telegram authorization data has expired")
    try:
        user_data = json.loads(values["user"])
        return TelegramUser(
            id=int(user_data["id"]),
            first_name=str(user_data.get("first_name") or "Telegram user"),
            username=user_data.get("username"),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Telegram user data") from exc

def authenticated_user(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
) -> TelegramUser:
    if not x_telegram_init_data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram authorization is required")
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "BOT_TOKEN is not configured")
    try:
        return validate_init_data(x_telegram_init_data, token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
