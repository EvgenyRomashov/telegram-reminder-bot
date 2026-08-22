"""Short-lived authorization tokens for personalized Mini App links."""

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit, urlunsplit

LAUNCH_TOKEN_MAX_AGE = 3600

def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")

def create_launch_token(user_id: int, bot_token: str, now: int | None = None) -> str:
    issued_at = int(time.time()) if now is None else now
    payload = f"{user_id}:{issued_at}:{secrets.token_urlsafe(8)}".encode()
    signature = hmac.new(bot_token.encode(), payload, hashlib.sha256).digest()
    return f"{_encode(payload)}.{_encode(signature)}"

def validate_launch_token(token: str, bot_token: str, now: int | None = None) -> int:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        expected = hmac.new(bot_token.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid launch token")
        user_id_text, issued_at_text, _ = payload.decode().split(":", 2)
        user_id = int(user_id_text)
        issued_at = int(issued_at_text)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid launch token") from exc
    current_time = int(time.time()) if now is None else now
    if issued_at > current_time + 30 or current_time - issued_at > LAUNCH_TOKEN_MAX_AGE:
        raise ValueError("Launch token has expired")
    return user_id

def personalized_launch_url(url: str, user_id: int, bot_token: str) -> str:
    parts = urlsplit(url)
    token = create_launch_token(user_id, bot_token)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, f"launch_token={token}"))
