"""Database initialization and session management for SQLModel with async support."""

import os

from loguru import logger
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from .agent import config

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL") or config.server.session.database_url
engine = create_async_engine(DATABASE_URL) if DATABASE_URL else None


async def init_db() -> None:
    """
    Initialize the database by creating all tables defined in SQLModel models.

    This function should be called once at the start of the application.
    """
    if not engine:
        logger.warning("No database URL provided. Skipping database initialization.")
        return
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:
    """
    Get a new SQLAlchemy session.

    :return: A new SQLAlchemy session.
    """
    return AsyncSession(bind=engine, expire_on_commit=False)


__all__ = ["init_db", "get_session"]
