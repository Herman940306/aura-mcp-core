"""Conversation logging for audit and replay."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class ConversationLogger:
    """Log conversations to disk for audit and replay."""

    def __init__(self, log_dir: str = "logs/conversations"):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # Backwards/forwards compatibility: expose logs_dir attribute used by tests
    @property
    def log_dir(self) -> Path:
        return self._log_dir

    @log_dir.setter
    def log_dir(self, value: Path | str) -> None:
        self._log_dir = Path(value)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def logs_dir(self) -> Path:
        return self._log_dir

    @logs_dir.setter
    def logs_dir(self, value: Path | str) -> None:
        self.log_dir = value

    def log_conversation(
        self,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Log a conversation.

        Args:
            messages: List of message dictionaries
            metadata: Optional metadata (models, user_id, etc.)

        Returns:
            Conversation ID (UUID)
        """
        conversation_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        conversation_data = {
            "id": conversation_id,
            "timestamp": timestamp,
            "messages": messages,
            "metadata": metadata or {},
            "provenance": {"logged_at": timestamp, "version": "1.0"},
        }

        # Write to file
        log_file = self._log_dir / f"{conversation_id}.json"
        with open(log_file, "w") as f:
            json.dump(conversation_data, f, indent=2)

        return conversation_id

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """Retrieve a conversation by ID."""
        log_file = self._log_dir / f"{conversation_id}.json"

        if not log_file.exists():
            return None

        with open(log_file) as f:
            return json.load(f)

    def list_conversations(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        List recent conversations.

        Args:
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of conversation summaries
        """
        log_files = sorted(
            self._log_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        summaries = []
        for log_file in log_files[offset : offset + limit]:
            try:
                with open(log_file) as f:
                    data = json.load(f)
                    summaries.append(
                        {
                            "id": data["id"],
                            "timestamp": data["timestamp"],
                            "message_count": len(data.get("messages", [])),
                            "metadata": data.get("metadata", {}),
                        }
                    )
            except Exception:
                continue

        return summaries
