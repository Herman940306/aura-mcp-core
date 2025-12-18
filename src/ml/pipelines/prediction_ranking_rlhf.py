"""
Prediction Ranking RLHF Pipeline

Implements Reinforcement Learning from Human Feedback for ranking predictions.
Learns from user interactions to improve prediction quality over time.

Features:
- Multi-armed bandit approach for exploration/exploitation
- Thompson Sampling for uncertainty-aware ranking
- PostgreSQL persistence for learning data
- Real-time reward calculation
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Try to import asyncpg for PostgreSQL persistence
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg not available - RLHF data will not persist")


@dataclass
class RewardWeights:
    """Configurable weights for reward calculation."""
    acceptance_weight: float = 0.4
    execution_success_weight: float = 0.2
    satisfaction_weight: float = 0.2
    adoption_speed_weight: float = 0.1
    routine_formation_weight: float = 0.1
    
    def to_dict(self) -> dict:
        return {
            "acceptance_weight": self.acceptance_weight,
            "execution_success_weight": self.execution_success_weight,
            "satisfaction_weight": self.satisfaction_weight,
            "adoption_speed_weight": self.adoption_speed_weight,
            "routine_formation_weight": self.routine_formation_weight,
        }


@dataclass
class PredictionOutcome:
    """Records the outcome of a prediction for RLHF learning."""
    prediction_id: str
    prediction_type: str
    prediction_text: str
    confidence: float
    user_accepted: bool
    execution_success: bool = True
    time_to_adoption_hours: float = 0.0
    user_satisfaction: float = 0.5
    routine_formed: bool = False
    energy_saved_kwh: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def calculate_reward(self, weights: RewardWeights) -> float:
        """Calculate reward signal from outcome."""
        reward = 0.0
        
        # Acceptance reward (binary)
        if self.user_accepted:
            reward += weights.acceptance_weight
        
        # Execution success reward
        if self.execution_success:
            reward += weights.execution_success_weight
        
        # Satisfaction reward (0-1 scale)
        reward += weights.satisfaction_weight * self.user_satisfaction
        
        # Adoption speed reward (faster = better, max 24h)
        if self.time_to_adoption_hours > 0:
            speed_factor = max(0, 1 - (self.time_to_adoption_hours / 24))
            reward += weights.adoption_speed_weight * speed_factor
        
        # Routine formation bonus
        if self.routine_formed:
            reward += weights.routine_formation_weight
        
        return min(1.0, max(0.0, reward))
    
    def to_dict(self) -> dict:
        return {
            "prediction_id": self.prediction_id,
            "prediction_type": self.prediction_type,
            "prediction_text": self.prediction_text,
            "confidence": self.confidence,
            "user_accepted": self.user_accepted,
            "execution_success": self.execution_success,
            "time_to_adoption_hours": self.time_to_adoption_hours,
            "user_satisfaction": self.user_satisfaction,
            "routine_formed": self.routine_formed,
            "energy_saved_kwh": self.energy_saved_kwh,
            "timestamp": self.timestamp,
        }


@dataclass
class PredictionStats:
    """Statistics for a prediction type (multi-armed bandit arm)."""
    prediction_type: str
    alpha: float = 1.0  # Beta distribution alpha (successes + 1)
    beta: float = 1.0   # Beta distribution beta (failures + 1)
    total_rewards: float = 0.0
    total_outcomes: int = 0
    avg_confidence: float = 0.5
    
    @property
    def mean_reward(self) -> float:
        """Expected reward (mean of Beta distribution)."""
        return self.alpha / (self.alpha + self.beta)
    
    @property
    def variance(self) -> float:
        """Uncertainty in reward estimate."""
        ab = self.alpha + self.beta
        return (self.alpha * self.beta) / (ab * ab * (ab + 1))
    
    def sample(self) -> float:
        """Thompson Sampling: sample from posterior."""
        return np.random.beta(self.alpha, self.beta)
    
    def update(self, reward: float) -> None:
        """Update statistics with new outcome."""
        self.total_rewards += reward
        self.total_outcomes += 1
        
        # Update Beta distribution parameters
        # Treat reward as probability of success
        self.alpha += reward
        self.beta += (1 - reward)
    
    def to_dict(self) -> dict:
        return {
            "prediction_type": self.prediction_type,
            "alpha": self.alpha,
            "beta": self.beta,
            "mean_reward": self.mean_reward,
            "variance": self.variance,
            "total_outcomes": self.total_outcomes,
            "avg_confidence": self.avg_confidence,
        }


class PredictionRankerRLHF:
    """
    RLHF-based prediction ranker using Thompson Sampling.
    
    Uses a multi-armed bandit approach where each prediction type
    is an "arm" with learned reward distribution.
    """
    
    def __init__(
        self,
        reward_weights: Optional[RewardWeights] = None,
        exploration_bonus: float = 0.1,
        db_url: Optional[str] = None,
    ):
        self.reward_weights = reward_weights or RewardWeights()
        self.exploration_bonus = exploration_bonus
        self.db_url = db_url or os.getenv("DATABASE_URL", "")
        
        # Per-type statistics (multi-armed bandit arms)
        self.type_stats: dict[str, PredictionStats] = {}
        
        # Outcome history for analysis
        self.outcomes: list[PredictionOutcome] = []
        
        # Metrics
        self.total_rankings = 0
        self.total_outcomes_recorded = 0
        
        logger.info("PredictionRankerRLHF initialized")
    
    def _get_or_create_stats(self, prediction_type: str) -> PredictionStats:
        """Get or create statistics for a prediction type."""
        if prediction_type not in self.type_stats:
            self.type_stats[prediction_type] = PredictionStats(
                prediction_type=prediction_type
            )
        return self.type_stats[prediction_type]
    
    def rank_predictions(
        self,
        candidates: list[dict[str, Any]],
        use_thompson_sampling: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Rank predictions using RLHF-learned preferences.
        
        Args:
            candidates: List of prediction candidates with at least:
                - prediction_type: str
                - confidence: float
            use_thompson_sampling: If True, use Thompson Sampling for
                exploration. If False, use greedy (mean reward).
        
        Returns:
            Sorted list of candidates with added 'rlhf_score' field.
        """
        self.total_rankings += 1
        
        scored_candidates = []
        for candidate in candidates:
            pred_type = candidate.get("prediction_type", "unknown")
            confidence = candidate.get("confidence", 0.5)
            
            stats = self._get_or_create_stats(pred_type)
            
            # Calculate RLHF score
            if use_thompson_sampling:
                # Thompson Sampling: sample from posterior
                learned_score = stats.sample()
            else:
                # Greedy: use mean reward
                learned_score = stats.mean_reward
            
            # Combine learned score with confidence
            # Higher confidence predictions get slight boost
            combined_score = (
                0.7 * learned_score +
                0.3 * confidence +
                self.exploration_bonus * stats.variance  # Exploration bonus
            )
            
            scored_candidate = {
                **candidate,
                "rlhf_score": round(combined_score, 4),
                "learned_reward": round(learned_score, 4),
                "uncertainty": round(stats.variance, 4),
            }
            scored_candidates.append(scored_candidate)
        
        # Sort by RLHF score (descending)
        scored_candidates.sort(key=lambda x: x["rlhf_score"], reverse=True)
        
        return scored_candidates
    
    def record_outcome(self, outcome: PredictionOutcome) -> float:
        """
        Record prediction outcome and update model.
        
        Args:
            outcome: The outcome to record
            
        Returns:
            Calculated reward value
        """
        self.total_outcomes_recorded += 1
        
        # Calculate reward
        reward = outcome.calculate_reward(self.reward_weights)
        
        # Update statistics for this prediction type
        stats = self._get_or_create_stats(outcome.prediction_type)
        stats.update(reward)
        
        # Update average confidence tracking
        n = stats.total_outcomes
        stats.avg_confidence = (
            (stats.avg_confidence * (n - 1) + outcome.confidence) / n
        )
        
        # Store outcome
        self.outcomes.append(outcome)
        
        # Keep only last 1000 outcomes in memory
        if len(self.outcomes) > 1000:
            self.outcomes = self.outcomes[-1000:]
        
        logger.info(
            f"Recorded outcome for {outcome.prediction_type}: "
            f"reward={reward:.3f}, accepted={outcome.user_accepted}"
        )
        
        return reward
    
    def get_metrics(self) -> dict[str, Any]:
        """Get RLHF performance metrics."""
        # Calculate overall acceptance rate
        if self.outcomes:
            acceptance_rate = sum(
                1 for o in self.outcomes if o.user_accepted
            ) / len(self.outcomes)
            avg_reward = sum(
                o.calculate_reward(self.reward_weights) for o in self.outcomes
            ) / len(self.outcomes)
        else:
            acceptance_rate = 0.0
            avg_reward = 0.0
        
        return {
            "total_rankings": self.total_rankings,
            "total_outcomes": self.total_outcomes_recorded,
            "acceptance_rate": round(acceptance_rate, 3),
            "avg_reward": round(avg_reward, 3),
            "prediction_types": len(self.type_stats),
            "type_stats": {
                k: v.to_dict() for k, v in self.type_stats.items()
            },
            "reward_weights": self.reward_weights.to_dict(),
            "recent_outcomes": len(self.outcomes),
        }
    
    def get_best_prediction_types(self, top_k: int = 5) -> list[dict]:
        """Get the best performing prediction types."""
        sorted_types = sorted(
            self.type_stats.values(),
            key=lambda x: x.mean_reward,
            reverse=True
        )
        return [t.to_dict() for t in sorted_types[:top_k]]
    
    def export_learning_data(self) -> dict:
        """Export learning data for persistence."""
        return {
            "type_stats": {
                k: {
                    "alpha": v.alpha,
                    "beta": v.beta,
                    "total_rewards": v.total_rewards,
                    "total_outcomes": v.total_outcomes,
                    "avg_confidence": v.avg_confidence,
                }
                for k, v in self.type_stats.items()
            },
            "metrics": {
                "total_rankings": self.total_rankings,
                "total_outcomes": self.total_outcomes_recorded,
            },
            "exported_at": datetime.now().isoformat(),
        }
    
    def import_learning_data(self, data: dict) -> None:
        """Import previously exported learning data."""
        if "type_stats" in data:
            for pred_type, stats_data in data["type_stats"].items():
                stats = PredictionStats(
                    prediction_type=pred_type,
                    alpha=stats_data.get("alpha", 1.0),
                    beta=stats_data.get("beta", 1.0),
                    total_rewards=stats_data.get("total_rewards", 0.0),
                    total_outcomes=stats_data.get("total_outcomes", 0),
                    avg_confidence=stats_data.get("avg_confidence", 0.5),
                )
                self.type_stats[pred_type] = stats
        
        if "metrics" in data:
            self.total_rankings = data["metrics"].get("total_rankings", 0)
            self.total_outcomes_recorded = data["metrics"].get(
                "total_outcomes", 0
            )
        
        logger.info(
            f"Imported learning data: {len(self.type_stats)} prediction types"
        )


# Global singleton instance
_ranker: Optional[PredictionRankerRLHF] = None


def get_ranker() -> PredictionRankerRLHF:
    """Get or create the global RLHF ranker instance."""
    global _ranker
    if _ranker is None:
        _ranker = PredictionRankerRLHF()
    return _ranker
