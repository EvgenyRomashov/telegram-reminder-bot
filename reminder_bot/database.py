"""
Database models using SQLAlchemy.
"""
from sqlalchemy import create_engine, Column, Integer, String, Date, Time, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.engine.url import URL
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///reminders.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    username = Column(String, nullable=True)
    
    # User settings for notifications
    notification_time = Column(Time, default="09:00:00")
    timezone = Column(String, default="Europe/Moscow")
    notifications_enabled = Column(Boolean, default=True)

    contacts = relationship("Contact", back_populates="owner", cascade="all, delete-orphan")

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=False)
    contact_group = Column(String, default="Друзья")
    
    user_id = Column(Integer, ForeignKey("users.telegram_id"))
    owner = relationship("User", back_populates="contacts")

def get_db():
    """Database session provider."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
