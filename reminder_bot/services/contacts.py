"""Contact CRUD shared by Telegram handlers and the web application."""

from datetime import date

from reminder_bot.database import Contact, User, get_db


class ContactNotFoundError(LookupError):
    pass


def ensure_user(user_id: int, first_name: str, username: str | None = None) -> User:
    with get_db() as db:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user is None:
            user = User(telegram_id=user_id, first_name=first_name, username=username)
            db.add(user)
        else:
            if first_name:
                user.first_name = first_name
            if username is not None:
                user.username = username
        db.commit()
        db.refresh(user)
        return user


def list_contacts(user_id: int) -> list[Contact]:
    with get_db() as db:
        return (
            db.query(Contact)
            .filter(Contact.user_id == user_id)
            .order_by(Contact.birth_date.asc(), Contact.full_name.asc())
            .all()
        )


def create_contact(user_id: int, full_name: str, birth_date: date, contact_group: str) -> Contact:
    contact = Contact(
        user_id=user_id, full_name=full_name, birth_date=birth_date,
        contact_group=contact_group,
    )
    with get_db() as db:
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact


def update_contact(
    user_id: int, contact_id: int, full_name: str,
    birth_date: date, contact_group: str,
) -> Contact:
    with get_db() as db:
        contact = db.query(Contact).filter(
            Contact.id == contact_id, Contact.user_id == user_id
        ).first()
        if contact is None:
            raise ContactNotFoundError(contact_id)
        contact.full_name = full_name
        contact.birth_date = birth_date
        contact.contact_group = contact_group
        db.commit()
        db.refresh(contact)
        return contact


def delete_contact(user_id: int, contact_id: int) -> None:
    with get_db() as db:
        contact = db.query(Contact).filter(
            Contact.id == contact_id, Contact.user_id == user_id
        ).first()
        if contact is None:
            raise ContactNotFoundError(contact_id)
        db.delete(contact)
        db.commit()
