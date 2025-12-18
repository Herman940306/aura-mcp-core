#!/usr/bin/env python3
"""
Database Monitoring Service for Aura IA Dashboard

Provides real-time PostgreSQL database metrics including:
- Connection status and pool statistics
- Database size and table sizes
- Query performance metrics
- Slow query detection
- Connection health indicators

Project Creator: Herman Swanepoel
Document Version: 1.0
Last Updated: December 13, 2025
"""

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aura_ia.database_monitor")

# Try to import asyncpg for PostgreSQL monitoring
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg not available - database monitoring limited")


@dataclass
class DatabaseMonitorConfig:
    """Configuration for Database Monitor."""
    host: str = "aura-ia-postgres"
    port: int = 5432
    database: str = "aura_db"
    user: str = "Admin"
    password: str = ""
    connection_timeout: float = 10.0
    slow_query_threshold_ms: float = 100.0


class DatabaseMonitor:
    """
    Database monitoring service for PostgreSQL metrics collection.

    Collects:
    - Connection count and pool status
    - Database size
    - Table sizes
    - Slow queries (if pg_stat_statements available)
    - Connection health
    """

    def __init__(self, config: Optional[DatabaseMonitorConfig] = None):
        self.config = config or DatabaseMonitorConfig()
        self._pool: Optional[asyncpg.Pool] = None
        self._connection_string = self._build_connection_string()

        logger.info(
            "DatabaseMonitor initialized: host=%s, db=%s, asyncpg=%s",
            self.config.host,
            self.config.database,
            ASYNCPG_AVAILABLE
        )

    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from config."""
        # Check for environment variable override
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url

        # Build from config
        if self.config.password:
            return (
                f"postgresql://{self.config.user}:{self.config.password}"
                f"@{self.config.host}:{self.config.port}/{self.config.database}"
            )
        return (
            f"postgresql://{self.config.user}"
            f"@{self.config.host}:{self.config.port}/{self.config.database}"
        )

    async def _get_connection(self) -> Optional[asyncpg.Connection]:
        """Get a database connection."""
        if not ASYNCPG_AVAILABLE:
            return None

        try:
            conn = await asyncpg.connect(
                self._connection_string,
                timeout=self.config.connection_timeout
            )
            return conn
        except Exception as e:
            logger.warning("Failed to connect to database: %s", e)
            return None

    async def get_database_metrics(self) -> Dict[str, Any]:
        """
        Collect all database metrics.

        Returns comprehensive database metrics dictionary.
        """
        if not ASYNCPG_AVAILABLE:
            return {
                "error": "asyncpg not available",
                "status": "unavailable",
                "timestamp": datetime.now(UTC).isoformat()
            }

        conn = await self._get_connection()
        if not conn:
            return {
                "error": "Could not connect to database",
                "status": "disconnected",
                "timestamp": datetime.now(UTC).isoformat()
            }

        try:
            metrics: Dict[str, Any] = {
                "status": "connected",
                "timestamp": datetime.now(UTC).isoformat(),
                "host": self.config.host,
                "database": self.config.database
            }

            # Connection count
            metrics["connections"] = await self._get_connection_stats(conn)

            # Database size
            metrics["database_size"] = await self._get_database_size(conn)

            # Table sizes
            metrics["table_sizes"] = await self._get_table_sizes(conn)

            # Slow queries (if available)
            slow_queries = await self._get_slow_queries(conn)
            if slow_queries:
                metrics["slow_queries"] = slow_queries

            # Database health
            metrics["health"] = await self._get_health_indicators(conn)

            return metrics

        except Exception as e:
            logger.error("Error collecting database metrics: %s", e)
            return {
                "error": str(e),
                "status": "error",
                "timestamp": datetime.now(UTC).isoformat()
            }
        finally:
            await conn.close()

    async def _get_connection_stats(
        self, conn: asyncpg.Connection
    ) -> Dict[str, Any]:
        """Get connection statistics."""
        try:
            # Active connections
            active = await conn.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
            )

            # Total connections
            total = await conn.fetchval(
                "SELECT count(*) FROM pg_stat_activity"
            )

            # Idle connections
            idle = await conn.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle'"
            )

            # Max connections setting
            max_conn = await conn.fetchval("SHOW max_connections")

            return {
                "active": active or 0,
                "idle": idle or 0,
                "total": total or 0,
                "max": int(max_conn) if max_conn else 100,
                "utilization_percent": round(
                    ((total or 0) / int(max_conn or 100)) * 100, 1
                )
            }
        except Exception as e:
            logger.warning("Error getting connection stats: %s", e)
            return {"error": str(e)}

    async def _get_database_size(
        self, conn: asyncpg.Connection
    ) -> Dict[str, Any]:
        """Get database size information."""
        try:
            # Database size
            size_bytes = await conn.fetchval(
                "SELECT pg_database_size(current_database())"
            )

            # Pretty size
            size_pretty = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )

            return {
                "bytes": size_bytes or 0,
                "pretty": size_pretty or "0 bytes",
                "mb": round((size_bytes or 0) / (1024 * 1024), 2)
            }
        except Exception as e:
            logger.warning("Error getting database size: %s", e)
            return {"error": str(e)}

    async def _get_table_sizes(
        self, conn: asyncpg.Connection
    ) -> List[Dict[str, Any]]:
        """Get table size information."""
        try:
            rows = await conn.fetch("""
                SELECT
                    schemaname,
                    tablename,
                    pg_total_relation_size(
                        schemaname || '.' || tablename
                    ) as size_bytes,
                    pg_size_pretty(
                        pg_total_relation_size(schemaname || '.' || tablename)
                    ) as size_pretty
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(
                    schemaname || '.' || tablename
                ) DESC
                LIMIT 20
            """)

            return [
                {
                    "schema": row["schemaname"],
                    "table": row["tablename"],
                    "size_bytes": row["size_bytes"],
                    "size_pretty": row["size_pretty"]
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning("Error getting table sizes: %s", e)
            return []

    async def _get_slow_queries(
        self, conn: asyncpg.Connection
    ) -> List[Dict[str, Any]]:
        """Get slow queries from pg_stat_statements if available."""
        try:
            # Check if pg_stat_statements is available
            ext_exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                )
            """)

            if not ext_exists:
                return []

            rows = await conn.fetch(f"""
                SELECT
                    query,
                    calls,
                    total_exec_time as total_time,
                    mean_exec_time as mean_time,
                    rows
                FROM pg_stat_statements
                WHERE mean_exec_time > {self.config.slow_query_threshold_ms}
                ORDER BY mean_exec_time DESC
                LIMIT 10
            """)

            return [
                {
                    "query": row["query"][:200],  # Truncate long queries
                    "calls": row["calls"],
                    "total_time_ms": round(row["total_time"], 2),
                    "mean_time_ms": round(row["mean_time"], 2),
                    "rows": row["rows"]
                }
                for row in rows
            ]
        except Exception as e:
            logger.debug("pg_stat_statements not available: %s", e)
            return []

    async def _get_health_indicators(
        self, conn: asyncpg.Connection
    ) -> Dict[str, Any]:
        """Get database health indicators."""
        try:
            # Check if database is accepting connections
            accepting = await conn.fetchval(
                "SELECT datallowconn FROM pg_database "
                "WHERE datname = current_database()"
            )

            # Get uptime (approximate via backend start time)
            uptime = await conn.fetchval(
                "SELECT now() - pg_postmaster_start_time()"
            )

            # Check for long-running queries
            long_running = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state = 'active'
                AND now() - query_start > interval '30 seconds'
            """)

            # Check for blocked queries
            blocked = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_activity
                WHERE wait_event_type = 'Lock'
            """)

            return {
                "accepting_connections": accepting,
                "uptime_seconds": uptime.total_seconds() if uptime else 0,
                "long_running_queries": long_running or 0,
                "blocked_queries": blocked or 0,
                "status": "healthy" if accepting and (blocked or 0) == 0
                else "degraded"
            }
        except Exception as e:
            logger.warning("Error getting health indicators: %s", e)
            return {"status": "unknown", "error": str(e)}

    async def check_connection(self) -> Dict[str, Any]:
        """Quick connection health check."""
        if not ASYNCPG_AVAILABLE:
            return {
                "connected": False,
                "error": "asyncpg not available"
            }

        try:
            conn = await self._get_connection()
            if conn:
                version = await conn.fetchval("SELECT version()")
                await conn.close()
                return {
                    "connected": True,
                    "version": version,
                    "timestamp": datetime.now(UTC).isoformat()
                }
            return {
                "connected": False,
                "error": "Connection failed"
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }


# Global database monitor instance
_database_monitor: Optional[DatabaseMonitor] = None


def get_database_monitor(
    config: Optional[DatabaseMonitorConfig] = None
) -> DatabaseMonitor:
    """Get or create the global database monitor instance."""
    global _database_monitor
    if _database_monitor is None:
        _database_monitor = DatabaseMonitor(config)
    return _database_monitor
