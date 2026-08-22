"""Telegram Mini App authentication."""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Header, HTTPException, status
from reminder_bot.web.launch import validate_launch_token

TELEGRAM_ED25519_PUBLIC_KEY = bytes.fromhex(
    "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d"
)
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

def _valid_ed25519_signature(
    values: dict[str, str], signature: str | None, bot_token: str
) -> bool:
    if not signature:
        return False
    try:
        bot_id = str(int(bot_token.split(":", 1)[0]))
        payload = {key: value for key, value in values.items() if key != "signature"}
        data_check_string = "\\n".join(
            f"{key}={value}" for key, value in sorted(payload.items())
        )
        signed_data = f"{bot_id}:WebAppData\\n{data_check_string}".encode()
        padding = "=" * (-len(signature) % 4)
        signature_bytes = base64.urlsafe_b64decode(signature + padding)
        Ed25519PublicKey.from_public_bytes(TELEGRAM_ED25519_PUBLIC_KEY).verify(
            signature_bytes, signed_data
        )
        return True
    except (ValueError, TypeError, InvalidSignature):
        return False

def validate_init_data(init_data: str, bot_token: str, now: int | None = None) -> TelegramUser:
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", None)
    if not received_hash:
        raise ValueError("Telegram hash is missing")

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    without_signature = {key: value for key, value in values.items() if key != "signature"}
    calculated_without = _hmac_hash(without_signature, secret_key)
    calculated_with = _hmac_hash(values, secret_key)
    valid_hmac = (
        hmac.compare_digest(calculated_without, received_hash)
        or hmac.compare_digest(calculated_with, received_hash)
    )
    valid_ed25519 = _valid_ed25519_signature(
        values, values.get("signature"), bot_token
    )
    if not valid_hmac and not valid_ed25519:
        logger.warning(
            "Telegram initData signature mismatch: fields=%s auth_date=%s "
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
    x_app_launch_token: str | None = Header(default=None, alias="X-App-Launch-Token"),
) -> TelegramUser:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "BOT_TOKEN is not configured")
    if x_telegram_init_data:
        try:
            return validate_init_data(x_telegram_init_data, token)
        except ValueError:
            pass
    if x_app_launch_token:
        try:
            user_id = validate_launch_token(x_app_launch_token, token)
            return TelegramUser(id=user_id, first_name="")
        except ValueError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram authorization is required")
