"""
Prediction Ranker RLHF Plugin
Adapted from HermesAI Copilot ULTRA for AI Home Assistant

Ranks AI predictions using reinforcement learning from human feedback
"""

import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from ml.pipelines.prediction_ranking_rlhf import PredictionOutcome, get_ranker
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import our existing ranker

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class PredictionCandidate(BaseModel):
    """Prediction candidate for ranking"""

    prediction_id: str
    prediction_type: str
    title: str
    description: str
    confidence: float
    context_richness: float = 0.5
    suggested_action: str = ""
    potential_benefit: str = ""


class RankingRequest(BaseModel):
    """Request to rank predictions"""

    candidates: list[dict[str, Any]]
    user_id: str = "default_user"


class RankingResponse(BaseModel):
    """Ranked predictions response"""

    ranked: list[dict[str, Any]]
    method: str = "rlhf"
    total_candidates: int


class OutcomeRecordRequest(BaseModel):
    """Request to record prediction outcome"""

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


class PredictionRankerRLHFPlugin:
    """
    RLHF-based prediction ranker adapted from HermesAI ULTRA

    Learns from user feedback to rank predictions by expected reward
    """

    def __init__(self):
        self.ranker = get_ranker()
        logger.info("PredictionRankerRLHFPlugin initialized")

    def rank_predictions(self, request: RankingRequest) -> RankingResponse:
        """
        Rank predictions using RLHF

        Args:
            request: Ranking request with candidates

        Returns:
            Ranked predictions
        """
        try:
            ranked = self.ranker.rank_predictions(request.candidates)

            return RankingResponse(
                ranked=ranked, method="rlhf", total_candidates=len(ranked)
            )

        except Exception as e:
            logger.error(f"Ranking failed: {e}")
            # Fallback to confidence-based ranking
            sorted_candidates = sorted(
                request.candidates,
                key=lambda x: x.get("confidence", 0.0),
                reverse=True,
            )
            return RankingResponse(
                ranked=sorted_candidates,
                method="fallback_confidence",
                total_candidates=len(sorted_candidates),
            )

    def record_outcome(self, request: OutcomeRecordRequest) -> dict:
        """Record prediction outcome for learning"""
        from datetime import datetime

        outcome = PredictionOutcome(
            prediction_id=request.prediction_id,
            prediction_type=request.prediction_type,
            prediction_text=request.prediction_text,
            confidence=request.confidence,
            user_accepted=request.user_accepted,
            execution_success=request.execution_success,
            time_to_adoption_hours=request.time_to_adoption_hours,
            user_satisfaction=request.user_satisfaction,
            routine_formed=request.routine_formed,
            energy_saved_kwh=request.energy_saved_kwh,
            timestamp=datetime.now().isoformat(),
        )

        self.ranker.record_outcome(outcome)
        reward = outcome.calculate_reward(self.ranker.reward_weights)

        return {
            "status": "recorded",
            "prediction_id": request.prediction_id,
            "calculated_reward": reward,
        }

    def get_metrics(self) -> dict:
        """Get RLHF metrics"""
        return self.ranker.get_metrics()


# Global plugin instance
_plugin: PredictionRankerRLHFPlugin | None = None


def get_prediction_ranker() -> PredictionRankerRLHFPlugin:
    """Get or create prediction ranker plugin"""
    global _plugin
    if _plugin is None:
        _plugin = PredictionRankerRLHFPlugin()
    return _plugin


# FastAPI app for standalone service
app = FastAPI(title="AI Assistant Prediction Ranker RLHF")


@app.post("/rank", response_model=RankingResponse)
async def rank(request: RankingRequest):
    """Rank predictions using RLHF"""
    service = get_prediction_ranker()
    return service.rank_predictions(request)


@app.post("/record_outcome")
async def record_outcome(request: OutcomeRecordRequest):
    """Record prediction outcome"""
    service = get_prediction_ranker()
    return service.record_outcome(request)


@app.get("/metrics")
async def metrics():
    """Get RLHF metrics"""
    service = get_prediction_ranker()
    return service.get_metrics()


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "service": "prediction_ranker_rlhf"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8092)
