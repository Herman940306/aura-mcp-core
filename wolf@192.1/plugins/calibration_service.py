"""
Calibration Service Plugin
Adapted from HermesAI Copilot ULTRA for AI Home Assistant

Maps raw ML prediction scores to calibrated probabilities
"""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from ml.pipelines.confidence_calibration import get_calibrator
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import our existing calibrator

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class CalibrationRequest(BaseModel):
    """Request for confidence calibration"""

    raw_prediction_score: float
    model_entropy: float = 0.0
    user_interaction_count: int = 0
    time_of_day_factor: float = 0.5
    historical_accuracy: float = 0.87
    context_richness: float = 0.5
    emotional_stability: float = 0.8
    routine_strength: float = 0.0


class CalibrationResponse(BaseModel):
    """Calibrated confidence response"""

    calibrated_probability: float
    raw_score: float
    method: str
    confidence_interval: tuple = (0.0, 1.0)


class CalibrationServicePlugin:
    """
    Calibration service adapted from HermesAI ULTRA

    Provides confidence calibration for AI predictions
    """

    def __init__(self, model_path: str | None = None):
        self.model_path = (
            model_path or "./data/calibration/calibrator_platt.pkl"
        )
        self.calibrator = get_calibrator()
        logger.info("CalibrationServicePlugin initialized")

    def calibrate(self, request: CalibrationRequest) -> CalibrationResponse:
        """
        Calibrate a prediction score

        Args:
            request: Calibration request with features

        Returns:
            Calibrated probability response
        """
        try:
            # Extract features
            prediction_data = {
                "raw_score": request.raw_prediction_score,
                "entropy": request.model_entropy,
                "interaction_count": request.user_interaction_count,
                "historical_accuracy": request.historical_accuracy,
                "context_richness": request.context_richness,
                "emotional_stability": request.emotional_stability,
                "routine_strength": request.routine_strength,
            }

            features = self.calibrator.extract_features(prediction_data)
            calibrated_prob = self.calibrator.calibrate(features)

            # Calculate confidence interval (simple approach)
            std_dev = 0.1  # Placeholder - should be from model
            ci_lower = max(0.0, calibrated_prob - 1.96 * std_dev)
            ci_upper = min(1.0, calibrated_prob + 1.96 * std_dev)

            return CalibrationResponse(
                calibrated_probability=calibrated_prob,
                raw_score=request.raw_prediction_score,
                method="platt_logistic",
                confidence_interval=(ci_lower, ci_upper),
            )

        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            # Fallback to raw score
            return CalibrationResponse(
                calibrated_probability=request.raw_prediction_score,
                raw_score=request.raw_prediction_score,
                method="fallback",
                confidence_interval=(0.0, 1.0),
            )

    def get_metrics(self) -> dict:
        """Get calibration metrics"""
        return self.calibrator.get_metrics()


# Global plugin instance
_plugin: CalibrationServicePlugin | None = None


def get_calibration_service() -> CalibrationServicePlugin:
    """Get or create calibration service plugin"""
    global _plugin
    if _plugin is None:
        _plugin = CalibrationServicePlugin()
    return _plugin


# FastAPI app for standalone service
app = FastAPI(title="AI Assistant Calibration Service")


@app.post("/score", response_model=CalibrationResponse)
async def score(request: CalibrationRequest):
    """Calibrate a prediction score"""
    service = get_calibration_service()
    return service.calibrate(request)


@app.get("/metrics")
async def metrics():
    """Get calibration metrics"""
    service = get_calibration_service()
    return service.get_metrics()


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "service": "calibration"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8091)
