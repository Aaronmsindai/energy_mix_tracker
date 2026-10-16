"""
Database connection and session management.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base

# Load .env file
load_dotenv()

# Try Streamlit secrets first (for cloud), then env var
try:
    import streamlit as st
    DB_URL = st.secrets["DATABASE_URL"]
except (KeyError, FileNotFoundError, ImportError):
    DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost/energy_tracker")
    # Force SQLAlchemy to use psycopg3 driver
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Force SQLAlchemy to use psycopg3
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)


engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Return a new session."""
    return SessionLocal()
