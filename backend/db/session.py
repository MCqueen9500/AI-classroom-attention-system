"""
backend/db/session.py
=====================
Asynchronous database session setup using SQLAlchemy 2.0.
Works seamlessly with:
- SQLite (aiosqlite) for local simulation/dev without installing database software.
- PostgreSQL (asyncpg) with TimescaleDB extension for production.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

# Create async engine based on database_url in settings
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    """Base model class for all SQLAlchemy declarative tables."""
    pass


async def init_db() -> None:
    """Creates all database tables defined in models.py."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI or worker tasks to yield an async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
