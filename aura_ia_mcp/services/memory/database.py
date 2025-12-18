"""
Aura IA Database Connection

PostgreSQL connection management with async support.
Uses SQLAlchemy 2.0+ async patterns.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """
    Get PostgreSQL connection URL from environment.

    Docker network (Production):
        postgresql+asyncpg://${POSTGRES_USER}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

    Host development:
        postgresql+asyncpg://${POSTGRES_USER}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}
    """
    host = os.getenv("POSTGRES_HOST", "aura-ia-postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "Admin")
    password = os.getenv("POSTGRES_PASSWORD", "")
    database = os.getenv("POSTGRES_DB", "aura_db")

    # Build URL (no password)
    if password:
        return (
            f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
        )
    return f"postgresql+asyncpg://{user}@{host}:{port}/{database}"


class DatabaseManager:
    """
    Async PostgreSQL database manager.

    Usage:
        db = DatabaseManager()
        await db.initialize()

        async with db.session() as session:
            result = await session.execute(...)

        await db.close()
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ):
        self._database_url = database_url or get_database_url()
        self._echo = echo
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = (
            None
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database connection pool."""
        if self._initialized:
            return

        logger.info(
            f"Initializing database connection to {self._database_url.split('@')[1]}"
        )

        self._engine = create_async_engine(
            self._database_url,
            echo=self._echo,
            pool_size=self._pool_size,
            max_overflow=self._max_overflow,
            pool_pre_ping=True,  # Verify connections before use
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        self._initialized = True
        logger.info("✅ Database connection pool initialized")

    async def close(self) -> None:
        """Close all database connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False
            logger.info("✅ Database connections closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session context manager.

        Usage:
            async with db.session() as session:
                result = await session.execute(select(User))
        """
        if not self._initialized:
            await self.initialize()

        if not self._session_factory:
            raise RuntimeError("Database not initialized")

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def health_check(self) -> dict:
        """Check database connectivity."""
        try:
            async with self.session() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()
            return {
                "status": "healthy",
                "database": "postgresql",
                "host": self._database_url.split("@")[1].split("/")[0],
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "database": "postgresql",
                "error": str(e),
            }

    async def create_tables(self) -> None:
        """Create all tables from models."""
        from .models import Base

        if not self._engine:
            await self.initialize()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("✅ Database tables created/verified")

    async def drop_tables(self) -> None:
        """Drop all tables (use with caution!)."""
        from .models import Base

        if not self._engine:
            await self.initialize()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        logger.warning("⚠️ All database tables dropped")


# Singleton instance
_db_manager: Optional[DatabaseManager] = None


async def get_database() -> DatabaseManager:
    """Get or create the database manager singleton."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Usage in routes:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_session)):
            ...
    """
    db = await get_database()
    async with db.session() as session:
        yield session


# =============================================================================
# Backwards Compatibility Aliases
# =============================================================================

# Alias for backwards compatibility
AuraMemoryDB = DatabaseManager


async def get_db() -> DatabaseManager:
    """
    Backwards-compatible alias for get_database().
    """
    return await get_database()
