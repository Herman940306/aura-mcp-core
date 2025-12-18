"""
Aura IA Database Initialization

Run this script to create/update the database schema.
Can be run standalone or imported and called programmatically.

Usage:
    python -m aura_ia_mcp.db.init_db

Or from code:
    from aura_ia_mcp.db.init_db import init_database
    await init_database()
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import asyncpg

from .schema import SCHEMA_SQL, SCHEMA_VERSION

logger = logging.getLogger(__name__)


def get_connection_params() -> dict:
    """Get PostgreSQL connection parameters from environment."""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "9208")),
        "user": os.getenv("POSTGRES_USER", "Admin"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "database": os.getenv("POSTGRES_DB", "aura_db"),
    }


async def check_connection(
    host: str, port: int, user: str, password: str, database: str
) -> bool:
    """Test database connectivity."""
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password if password else None,
            database=database,
            timeout=10,
        )
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False


async def check_schema_version(
    conn: asyncpg.Connection,
) -> Optional[str]:
    """Check current schema version in database."""
    try:
        result = await conn.fetchval(
            "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
        )
        return result
    except asyncpg.UndefinedTableError:
        return None


async def apply_schema(conn: asyncpg.Connection) -> bool:
    """Apply the full schema to the database."""
    try:
        await conn.execute(SCHEMA_SQL)
        logger.info(f"✅ Schema v{SCHEMA_VERSION} applied successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Schema application failed: {e}")
        return False


async def init_database(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> bool:
    """
    Initialize the database with the Aura IA schema.
    
    Args:
        host: PostgreSQL host (default: from env or localhost)
        port: PostgreSQL port (default: from env or 9208)
        user: PostgreSQL user (default: from env or Admin)
        password: PostgreSQL password (default: from env or empty)
        database: PostgreSQL database (default: from env or aura_db)
    
    Returns:
        True if successful, False otherwise
    """
    params = get_connection_params()
    
    # Override with provided values
    if host:
        params["host"] = host
    if port:
        params["port"] = port
    if user:
        params["user"] = user
    if password is not None:
        params["password"] = password
    if database:
        params["database"] = database
    
    logger.info(f"🔌 Connecting to PostgreSQL at {params['host']}:{params['port']}/{params['database']}")
    
    # Test connection
    if not await check_connection(**params):
        logger.error("❌ Cannot connect to PostgreSQL")
        return False
    
    # Connect and apply schema
    try:
        conn = await asyncpg.connect(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=params["password"] if params["password"] else None,
            database=params["database"],
        )
        
        # Check existing schema
        current_version = await check_schema_version(conn)
        
        if current_version:
            logger.info(f"📋 Current schema version: {current_version}")
            if current_version == SCHEMA_VERSION:
                logger.info("✅ Schema is up to date")
                await conn.close()
                return True
            else:
                logger.info(f"⬆️ Upgrading schema from {current_version} to {SCHEMA_VERSION}")
        else:
            logger.info("📋 No existing schema found, creating fresh")
        
        # Apply schema
        success = await apply_schema(conn)
        await conn.close()
        
        if success:
            logger.info("✅ Database initialization complete")
            logger.info(f"   Tables created: conversations, messages, model_rankings, debates, debate_rounds, learning_events, routing_history")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False


async def main():
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    print("=" * 60)
    print("AURA IA DATABASE INITIALIZATION")
    print(f"Schema Version: {SCHEMA_VERSION}")
    print("=" * 60)
    
    success = await init_database()
    
    if success:
        print("\n✅ Database ready!")
        sys.exit(0)
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
