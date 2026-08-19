import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import date, timedelta
from urllib.parse import urlencode

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from reminder_bot.database import Base, Contact, User
from reminder_bot.services import contacts as contact_service
from reminder_bot.web.app import ContactPayload
from reminder_bot.web.auth import validate_init_data


def signed_init_data(token: str, user_id: int, auth_date: int) -> str:
    values = {
        "auth_date": str(auth_date),
        "query_id": "query-1",
        "user": json.dumps(
            {"id": user_id, "first_name": "Иван", "username": "ivan"},
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    }
    check_string = "\\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_validate_init_data_accepts_valid_signature():
    data = signed_init_data("123:token", 42, 1_700_000_000)
    user = validate_init_data(data, "123:token", now=1_700_000_100)
    assert user.id == 42
    assert user.username == "ivan"


def test_validate_init_data_rejects_tampering():
    data = signed_init_data("123:token", 42, 1_700_000_000).replace("%3A42", "%3A99", 1)
    with pytest.raises(ValueError, match="signature"):
        validate_init_data(data, "123:token", now=1_700_000_100)


def test_validate_init_data_rejects_expired_data():
    data = signed_init_data("123:token", 42, 1_700_000_000)
    with pytest.raises(ValueError, match="expired"):
        validate_init_data(data, "123:token", now=1_700_100_000)


def test_contact_payload_normalizes_and_validates():
    payload = ContactPayload(
        full_name="  Иван   Иванов ",
        birth_date=date(2000, 1, 1),
        contact_group="Семья",
    )
    assert payload.full_name == "Иван Иванов"
    with pytest.raises(ValueError):
        ContactPayload(
            full_name="Иван", birth_date=date.today() + timedelta(days=1),
            contact_group="Друзья",
        )


@pytest.fixture
def service_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    @contextmanager
    def test_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(contact_service, "get_db", test_get_db)
    return session_factory


def test_contact_service_isolates_users(service_db):
    contact_service.ensure_user(1, "Первый")
    contact_service.ensure_user(2, "Второй")
    first = contact_service.create_contact(1, "Иван", date(1990, 1, 1), "Друзья")
    second = contact_service.create_contact(2, "Анна", date(1991, 2, 2), "Семья")

    assert [contact.id for contact in contact_service.list_contacts(1)] == [first.id]
    assert [contact.id for contact in contact_service.list_contacts(2)] == [second.id]
    with pytest.raises(contact_service.ContactNotFoundError):
        contact_service.update_contact(1, second.id, "Чужой", date(1991, 2, 2), "Семья")
    with pytest.raises(contact_service.ContactNotFoundError):
        contact_service.delete_contact(1, second.id)



@pytest.mark.asyncio
async def test_contacts_api_requires_telegram_auth(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from reminder_bot.web.app import app

    monkeypatch.setenv("BOT_TOKEN", "123:token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/contacts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_contacts_api_uses_authenticated_user(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    import reminder_bot.web.app as web_module
    from reminder_bot.web.auth import TelegramUser

    web_module.app.dependency_overrides[web_module.current_user] = lambda: TelegramUser(
        id=42, first_name="Иван"
    )
    monkeypatch.setattr(
        web_module, "list_contacts",
        lambda user_id: [Contact(
            id=7, user_id=user_id, full_name="Анна",
            birth_date=date(1990, 2, 3), contact_group="Семья",
        )],
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=web_module.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/contacts")
    finally:
        web_module.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["id"] == 7
    assert response.json()[0]["full_name"] == "Анна"
