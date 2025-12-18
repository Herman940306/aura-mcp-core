"""
Aura IA Database Module

PostgreSQL database utilities for persistent memory, conversation history,
model rankings, and debate engine storage.
"""

from .schema import SCHEMA_SQL, SCHEMA_VERSION
from .init_db import init_database, check_schema_version, apply_schema

__all__ = [
    "SCHEMA_SQL",
    "SCHEMA_VERSION",
    "init_database",
    "check_schema_version",
    "apply_schema",
]
