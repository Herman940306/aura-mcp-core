"""Episode Logger for SICD training loop persistence."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_EPISODES_DIR = "./data/training/episodes"


@dataclass
class EpisodeMetrics:
    """Metrics for a training episode."""

    tokens_used: int = 0
    inference_time_ms: float = 0.0
    changes_proposed: int = 0
    changes_accepted: int = 0
    rag_queries: int = 0
    llm_calls: int = 0
    error_count: int = 0


@dataclass
class TrainingEpisode:
    """Complete training episode record."""

    episode_id: str
    run_id: str
    episode_number: int
    started_at: str
    completed_at: str | None = None
    status: str = "in_progress"  # in_progress, completed, failed
    task_description: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    metrics: EpisodeMetrics = field(default_factory=EpisodeMetrics)
    metadata: dict[str, Any] = field(default_factory=dict)


class EpisodeLogger:
    """Manages persistence and retrieval of training episodes."""

    def __init__(self, episodes_dir: str | None = None):
        self.episodes_dir = Path(episodes_dir or DEFAULT_EPISODES_DIR)
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        self.current_episode: TrainingEpisode | None = None

    def start_episode(
        self,
        run_id: str,
        episode_number: int,
        task_description: str = "",
        context: dict[str, Any] | None = None,
    ) -> TrainingEpisode:
        """Start a new training episode.

        Args:
            run_id: Training run identifier
            episode_number: Episode sequence number
            task_description: Description of the task
            context: Additional context data

        Returns:
            New TrainingEpisode instance
        """
        timestamp = datetime.utcnow().isoformat()
        episode_id = f"{run_id}_ep{episode_number:04d}"

        episode = TrainingEpisode(
            episode_id=episode_id,
            run_id=run_id,
            episode_number=episode_number,
            started_at=timestamp,
            task_description=task_description,
            context=context or {},
            status="in_progress",
        )

        self.current_episode = episode
        self._save_episode(episode)
        logger.info(f"Started episode {episode_id}")
        return episode

    def log_action(
        self, action_type: str, action_data: dict[str, Any]
    ) -> None:
        """Log an action taken during the episode.

        Args:
            action_type: Type of action (e.g., 'code_generation', 'rag_query')
            action_data: Action-specific data
        """
        if not self.current_episode:
            logger.warning("No active episode to log action")
            return

        action_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": action_type,
            "data": action_data,
        }

        self.current_episode.actions.append(action_record)
        self._save_episode(self.current_episode)

    def log_outcome(
        self, outcome_type: str, outcome_data: dict[str, Any]
    ) -> None:
        """Log an outcome or result from the episode.

        Args:
            outcome_type: Type of outcome (e.g., 'pr_created', 'test_passed')
            outcome_data: Outcome-specific data
        """
        if not self.current_episode:
            logger.warning("No active episode to log outcome")
            return

        outcome_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": outcome_type,
            "data": outcome_data,
        }

        self.current_episode.outcomes.append(outcome_record)
        self._save_episode(self.current_episode)

    def update_metrics(self, **kwargs: Any) -> None:
        """Update episode metrics.

        Args:
            **kwargs: Metric fields to update (e.g., tokens_used=100)
        """
        if not self.current_episode:
            logger.warning("No active episode to update metrics")
            return

        for key, value in kwargs.items():
            if hasattr(self.current_episode.metrics, key):
                current = getattr(self.current_episode.metrics, key)
                if isinstance(current, (int, float)):
                    setattr(self.current_episode.metrics, key, current + value)
                else:
                    setattr(self.current_episode.metrics, key, value)

        self._save_episode(self.current_episode)

    def complete_episode(
        self, status: str = "completed", metadata: dict[str, Any] | None = None
    ) -> TrainingEpisode:
        """Complete the current episode.

        Args:
            status: Final status (completed, failed)
            metadata: Additional metadata to store

        Returns:
            Completed TrainingEpisode
        """
        if not self.current_episode:
            raise ValueError("No active episode to complete")

        self.current_episode.completed_at = datetime.utcnow().isoformat()
        self.current_episode.status = status

        if metadata:
            self.current_episode.metadata.update(metadata)

        self._save_episode(self.current_episode)
        logger.info(
            f"Completed episode {self.current_episode.episode_id} with status: {status}"
        )

        completed = self.current_episode
        self.current_episode = None
        return completed

    def _save_episode(self, episode: TrainingEpisode) -> None:
        """Save episode to disk."""
        file_path = self.episodes_dir / f"{episode.episode_id}.json"

        # Convert dataclass to dict
        episode_dict = asdict(episode)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(episode_dict, f, indent=2)
        except Exception as e:
            logger.exception(
                f"Failed to save episode {episode.episode_id}: {e}"
            )

    def load_episode(self, episode_id: str) -> TrainingEpisode | None:
        """Load episode from disk.

        Args:
            episode_id: Episode identifier

        Returns:
            TrainingEpisode if found, None otherwise
        """
        file_path = self.episodes_dir / f"{episode_id}.json"

        if not file_path.exists():
            logger.warning(f"Episode file not found: {episode_id}")
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Reconstruct metrics
            metrics_data = data.pop("metrics", {})
            metrics = EpisodeMetrics(**metrics_data)

            # Reconstruct episode
            episode = TrainingEpisode(**data, metrics=metrics)
            return episode

        except Exception as e:
            logger.exception(f"Failed to load episode {episode_id}: {e}")
            return None

    def list_episodes(self, run_id: str | None = None) -> list[str]:
        """List all episode IDs, optionally filtered by run_id.

        Args:
            run_id: Optional run ID filter

        Returns:
            List of episode IDs
        """
        episodes = []

        for file_path in self.episodes_dir.glob("*.json"):
            episode_id = file_path.stem

            if run_id and not episode_id.startswith(run_id):
                continue

            episodes.append(episode_id)

        return sorted(episodes)

    def get_run_summary(self, run_id: str) -> dict[str, Any]:
        """Get summary statistics for a training run.

        Args:
            run_id: Training run identifier

        Returns:
            Summary dict with aggregated metrics
        """
        episode_ids = self.list_episodes(run_id=run_id)

        total_episodes = len(episode_ids)
        completed = 0
        failed = 0
        total_tokens = 0
        total_changes = 0
        total_actions = 0

        for episode_id in episode_ids:
            episode = self.load_episode(episode_id)
            if not episode:
                continue

            if episode.status == "completed":
                completed += 1
            elif episode.status == "failed":
                failed += 1

            total_tokens += episode.metrics.tokens_used
            total_changes += episode.metrics.changes_proposed
            total_actions += len(episode.actions)

        return {
            "run_id": run_id,
            "total_episodes": total_episodes,
            "completed": completed,
            "failed": failed,
            "in_progress": total_episodes - completed - failed,
            "total_tokens_used": total_tokens,
            "total_changes_proposed": total_changes,
            "total_actions": total_actions,
        }


# Global instance
_episode_logger: EpisodeLogger | None = None


def get_episode_logger() -> EpisodeLogger:
    """Get or create global episode logger instance."""
    global _episode_logger
    if _episode_logger is None:
        _episode_logger = EpisodeLogger()
    return _episode_logger


def log_episode(data: dict) -> None:
    """Legacy function for backward compatibility.

    Args:
        data: Episode data to log
    """
    logger_instance = get_episode_logger()

    if "action" in data:
        logger_instance.log_action(data.get("action_type", "unknown"), data)
    elif "outcome" in data:
        logger_instance.log_outcome(data.get("outcome_type", "unknown"), data)
    else:
        logger.info(f"Logged episode data: {data}")
