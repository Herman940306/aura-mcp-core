"""Conversation Persistence Store for Aura IA MCP.

Provides SQLite-based persistence for conversation history,
enabling the model to "remember" past interactions and build context.

PRD Compliance:
- Persists conversation history for model context
- Integrates with ConversationGovernance for PII redaction
- Hash chain integrity for audit trail
- Configurable retention period

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import governance for PII detection
from mcp_server.conversation_governance import ConversationGovernance


@dataclass
class ConversationMessage:
    """A single message in the conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_call: dict | None = None
    tool_result: dict | None = None
    message_id: int | None = None  # Database row ID


@dataclass
class Conversation:
    """Manages conversation history and context with persistence."""

    id: str
    messages: deque = field(default_factory=lambda: deque(maxlen=50))
    mode: str = "general"
    created_at: float = field(default_factory=time.time)
    _store: ConversationStore | None = field(default=None, repr=False)

    def add_message(
        self, role: str, content: str, **kwargs
    ) -> ConversationMessage:
        """Add a message and persist to store."""
        msg = ConversationMessage(role=role, content=content, **kwargs)
        self.messages.append(msg)

        # Persist to SQLite if store available
        if self._store:
            msg.message_id = self._store.save_message(
                conversation_id=self.id,
                role=role,
                content=content,
                timestamp=msg.timestamp,
                metadata=kwargs if kwargs else None,
            )

        return msg

    def get_messages_for_llm(self) -> list[dict[str, str]]:
        """Get messages formatted for the LLM."""
        return [
            {"role": m.role, "content": m.content}
            for m in self.messages
            if m.role in ("user", "assistant")
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "message_count": len(self.messages),
            "created_at": self.created_at,
        }


class ConversationStore:
    """SQLite-based persistence for conversations.

    Features:
    - Automatic database creation
    - Conversation history loading on restart
    - PII redaction via ConversationGovernance
    - Hash chain integrity tracking
    - Configurable retention period

    Usage:
        store = ConversationStore()
        store.initialize()

        # Get or create conversation with automatic persistence
        conv = store.get_or_create_conversation("user-123", mode="mcp")

        # Messages automatically saved when using conv.add_message()
        conv.add_message("user", "What's the time?")
        conv.add_message("assistant", "It's 3:45 PM.")

        # Load conversation history from previous sessions
        history = store.get_conversation_history("user-123", limit=100)
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        max_messages_per_conversation: int = 50,
        retention_days: int = 90,
        enable_pii_redaction: bool = True,
    ):
        """Initialize the conversation store.

        Args:
            db_path: Path to SQLite database file. Defaults to
                     data/conversations.db relative to project root.
            max_messages_per_conversation: Max messages to keep in memory.
            retention_days: Days to retain conversations before pruning.
            enable_pii_redaction: Enable PII detection and redaction.
        """
        if db_path is None:
            # Default to project data directory
            project_root = Path(__file__).parent.parent.parent.parent
            db_path = project_root / "data" / "conversations.db"

        self.db_path = Path(db_path)
        self.max_messages = max_messages_per_conversation
        self.retention_days = retention_days
        self.enable_pii_redaction = enable_pii_redaction

        # In-memory conversation cache
        self._conversations: dict[str, Conversation] = {}

        # Governance for PII and integrity
        self._governance: ConversationGovernance | None = None
        if enable_pii_redaction:
            try:
                log_dir = self.db_path.parent / "conversation_logs"
                self._governance = ConversationGovernance(
                    log_dir=log_dir,
                    retention_days=retention_days,
                    enable_pii_detection=True,
                )
            except Exception as e:
                print(f"⚠️ ConversationGovernance init failed: {e}")

        self._initialized = False

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with context management."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> bool:
        """Initialize the database schema.

        Creates:
        - conversations table: metadata for each conversation
        - messages table: individual messages with timestamps
        - Indexes for efficient querying

        Returns:
            True if initialization successful
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Conversations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    mode TEXT DEFAULT 'general',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    metadata TEXT
                )
            """
            )

            # Messages table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    pii_redacted INTEGER DEFAULT 0,
                    metadata TEXT,
                    hash TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """
            )

            # Indexes for performance
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, timestamp DESC)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                ON conversations(updated_at DESC)
            """
            )

            conn.commit()

        self._initialized = True
        print(f"✅ ConversationStore initialized at {self.db_path}")
        return True

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        timestamp: float | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Save a single message to the database.

        Args:
            conversation_id: Conversation identifier
            role: Message role (user, assistant, system, tool)
            content: Message content
            timestamp: Unix timestamp (defaults to now)
            metadata: Additional metadata dict

        Returns:
            Database row ID of the saved message
        """
        if not self._initialized:
            self.initialize()

        timestamp = timestamp or time.time()
        pii_redacted = False
        hash_value = None

        # Apply PII redaction if enabled
        if self._governance and self.enable_pii_redaction:
            result = self._governance.log_conversation_turn(
                conversation_id=conversation_id,
                trace_id=f"msg-{int(timestamp * 1000)}",
                role=role,
                content=content,
                metadata=metadata,
            )
            content = result.get("content", content)
            pii_redacted = bool(result.get("pii_tags"))
            hash_value = result.get("hash")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Ensure conversation exists
            cursor.execute(
                """
                INSERT OR IGNORE INTO conversations
                (id, mode, created_at, updated_at)
                VALUES (?, 'general', ?, ?)
            """,
                (conversation_id, timestamp, timestamp),
            )

            # Insert message
            cursor.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, timestamp, pii_redacted, metadata, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    conversation_id,
                    role,
                    content,
                    timestamp,
                    1 if pii_redacted else 0,
                    json.dumps(metadata) if metadata else None,
                    hash_value,
                ),
            )

            message_id = cursor.lastrowid

            # Update conversation metadata
            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = ?,
                    message_count = (
                        SELECT COUNT(*) FROM messages
                        WHERE conversation_id = ?
                    )
                WHERE id = ?
            """,
                (timestamp, conversation_id, conversation_id),
            )

            conn.commit()

        return message_id

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get message history for a conversation.

        Args:
            conversation_id: Conversation identifier
            limit: Max messages to return
            offset: Number of messages to skip (for pagination)

        Returns:
            List of message dicts sorted by timestamp (oldest first)
        """
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, role, content, timestamp, pii_redacted, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
            """,
                (conversation_id, limit, offset),
            )

            messages = []
            for row in cursor.fetchall():
                messages.append(
                    {
                        "id": row["id"],
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": row["timestamp"],
                        "pii_redacted": bool(row["pii_redacted"]),
                        "metadata": (
                            json.loads(row["metadata"])
                            if row["metadata"]
                            else None
                        ),
                    }
                )

            return messages

    def get_or_create_conversation(
        self,
        conversation_id: str,
        mode: str = "general",
    ) -> Conversation:
        """Get or create a conversation with persistence.

        Loads existing history from database if available.

        Args:
            conversation_id: Unique conversation identifier
            mode: Chat mode (general, mcp, ai, debug)

        Returns:
            Conversation instance with database persistence
        """
        if conversation_id in self._conversations:
            conv = self._conversations[conversation_id]
            conv.mode = mode
            return conv

        if not self._initialized:
            self.initialize()

        # Load existing conversation
        conv = Conversation(
            id=conversation_id,
            mode=mode,
            messages=deque(maxlen=self.max_messages),
            _store=self,
        )

        # Load history from database
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get conversation metadata
            cursor.execute(
                "SELECT mode, created_at FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            row = cursor.fetchone()
            if row:
                conv.mode = row["mode"]
                conv.created_at = row["created_at"]

            # Load recent messages
            history = self.get_conversation_history(
                conversation_id, limit=self.max_messages
            )
            for msg_data in history:
                msg = ConversationMessage(
                    role=msg_data["role"],
                    content=msg_data["content"],
                    timestamp=msg_data["timestamp"],
                    message_id=msg_data["id"],
                )
                conv.messages.append(msg)

        # Update mode in database
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE conversations SET mode = ? WHERE id = ?",
                (mode, conversation_id),
            )
            conn.commit()

        self._conversations[conversation_id] = conv

        print(
            f"📝 Loaded conversation {conversation_id} with {len(conv.messages)} messages"
        )
        return conv

    def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List all conversations.

        Args:
            limit: Max conversations to return
            offset: Number to skip (pagination)

        Returns:
            List of conversation metadata dicts
        """
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, mode, created_at, updated_at, message_count
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )

            return [dict(row) for row in cursor.fetchall()]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation to delete

        Returns:
            True if deleted, False if not found
        """
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete messages first (foreign key)
            cursor.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )

            # Delete conversation
            cursor.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )

            deleted = cursor.rowcount > 0
            conn.commit()

        # Remove from cache
        self._conversations.pop(conversation_id, None)

        return deleted

    def prune_old_conversations(self) -> dict[str, Any]:
        """Remove conversations older than retention period.

        Returns:
            Summary of pruning operation
        """
        if not self._initialized:
            self.initialize()

        cutoff = time.time() - (self.retention_days * 86400)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Count before
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_before = cursor.fetchone()[0]

            # Find old conversations
            cursor.execute(
                "SELECT id FROM conversations WHERE updated_at < ?",
                (cutoff,),
            )
            old_ids = [row[0] for row in cursor.fetchall()]

            # Delete messages for old conversations
            for conv_id in old_ids:
                cursor.execute(
                    "DELETE FROM messages WHERE conversation_id = ?",
                    (conv_id,),
                )
                self._conversations.pop(conv_id, None)

            # Delete old conversations
            cursor.execute(
                "DELETE FROM conversations WHERE updated_at < ?",
                (cutoff,),
            )

            conn.commit()

            # Count after
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_after = cursor.fetchone()[0]

        return {
            "pruned_count": len(old_ids),
            "total_before": total_before,
            "total_after": total_after,
            "retention_days": self.retention_days,
        }


# Singleton instance
_conversation_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    """Get or create the singleton conversation store."""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationStore()
        _conversation_store.initialize()
    return _conversation_store


__all__ = [
    "ConversationStore",
    "Conversation",
    "ConversationMessage",
    "get_conversation_store",
]
