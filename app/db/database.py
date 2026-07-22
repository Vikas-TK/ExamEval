"""
Database connection and engine configuration for Supabase PostgreSQL with local SQLite fallback.
"""

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

primary_db_url = settings.database_url or settings.supabase_db_url
fallback_db_url = "sqlite:///./exam_eval.db"


def create_db_engine(url: str) -> Engine:
    kwargs = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_recycle=1800,
        )
    return create_engine(url, **kwargs)


# Initialize engine with primary URL, falling back to local SQLite if primary connection fails
try:
    engine: Engine = create_db_engine(primary_db_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Successfully connected to primary database.")
except Exception as primary_exc:
    logger.warning(f"Primary database connection failed ({primary_exc}). Falling back to local SQLite ({fallback_db_url}).")
    engine: Engine = create_db_engine(fallback_db_url)


def check_database_connection() -> bool:
    """Verifies active connectivity to PostgreSQL / SQLite database."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error(f"Database connectivity check failed: {exc}")
        return False
