"""
Database connection and session management.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base


# Database URL - override with env var in production
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost/energy_tracker",
)

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Return a new session."""
    return SessionLocal()