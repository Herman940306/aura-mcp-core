# Aura IA Memory Service
# PostgreSQL-backed persistent memory for chat, tasks, patterns, and learning

from .database import (
    AuraMemoryDB,
    DatabaseManager,
    get_database,
    get_database_url,
    get_db,
    get_session,
)
from .models import (
    Base,
    BehavioralPattern,
    ChatLog,
    CodingSession,
    DebateHistory,
    DeviceState,
    MediaPreference,
    MediaWatchHistory,
    ModelLeaderboard,
    PredictionLog,
    ReasoningTrace,
    Task,
    ToolCall,
    UserProfile,
)

__all__ = [
    # Database
    "AuraMemoryDB",
    "DatabaseManager",
    "get_db",
    "get_database",
    "get_session",
    "get_database_url",
    # Models
    "Base",
    "ChatLog",
    "Task",
    "ReasoningTrace",
    "CodingSession",
    "ToolCall",
    "MediaWatchHistory",
    "MediaPreference",
    "DeviceState",
    "UserProfile",
    "BehavioralPattern",
    "PredictionLog",
    "ModelLeaderboard",
    "DebateHistory",
]
