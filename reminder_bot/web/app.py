"""Web application for the Telegram Mini App."""

from datetime import date
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from reminder_bot.database import Base, engine
from reminder_bot.services.contacts import (
    ContactNotFoundError,
    create_contact,
    delete_contact,
    ensure_user,
    list_contacts,
    update_contact,
)
from reminder_bot.web.auth import TelegramUser, authenticated_user

STATIC_DIR = Path(__file__).parent / "static"
ContactGroup = Literal["Семья", "Друзья", "Коллеги", "Знакомые", "Важное"]

class ContactPayload(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    birth_date: date
    contact_group: ContactGroup = "Друзья"

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Имя не может быть пустым")
        return normalized

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Дата рождения не может быть в будущем")
        return value

class ContactResponse(BaseModel):
    id: int
    full_name: str
    birth_date: date
    contact_group: str

def current_user(user: TelegramUser = Depends(authenticated_user)) -> TelegramUser:
    ensure_user(user.id, user.first_name, user.username)
    return user

AuthenticatedUser = Annotated[TelegramUser, Depends(current_user)]

@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="Birthday Reminder Mini App", docs_url=None, redoc_url=None, lifespan=lifespan
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/api/contacts", response_model=list[ContactResponse])
def get_contacts(user: AuthenticatedUser):
    return list_contacts(user.id)

@app.post("/api/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def post_contact(payload: ContactPayload, user: AuthenticatedUser):
    return create_contact(user.id, payload.full_name, payload.birth_date, payload.contact_group)

@app.put("/api/contacts/{contact_id}", response_model=ContactResponse)
def put_contact(contact_id: int, payload: ContactPayload, user: AuthenticatedUser):
    try:
        return update_contact(
            user.id, contact_id, payload.full_name, payload.birth_date,
            payload.contact_group,
        )
    except ContactNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контакт не найден") from exc

@app.delete("/api/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_contact(contact_id: int, user: AuthenticatedUser) -> None:
    try:
        delete_contact(user.id, contact_id)
    except ContactNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контакт не найден") from exc
