"""
Database models using SQLAlchemy.
"""
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Date, Time, Boolean, ForeignKey, BigInteger, event
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os
from contextlib import contextmanager
from datetime import time

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///reminders.db")

engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"timeout": 30}
engine = create_engine(DATABASE_URL, **engine_options)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    first_name = Column(String)
    username = Column(String, nullable=True)
    
    # User settings for notifications
    notification_time = Column(Time, default=time(9, 0))
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

@contextmanager
def get_db():
    """Database session provider."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
