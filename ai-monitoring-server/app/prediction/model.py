"""
model.py — Load, run inference, and manage the trained ML model.

This module:
  1. Loads the model from disk at server startup.
  2. Falls back to the baseline rule if the model is not yet trained.
  3. Exposes a single predict() function used by the metrics route.
  4. Caches the loaded model in memory (no re-loading per request).

The actual training is done by scripts/train.py (run offline after data collection).
"""
import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from app.config import MODEL_PATH, PREDICTION_THRESHOLD
from app.prediction import baseline as baseline_module
from app.prediction.features import FEATURE_NAMES

logger = logging.getLogger(__name__)

# ── Model cache ───────────────────────────────────────────────────────────────
_model = None                 # scikit-learn pipeline (StandardScaler + classifier)
_model_version: str = "none"  # set when model is loaded


def load_model() -> bool:
    """
    Load the model from MODEL_PATH into the module-level cache.
    Returns True if loaded successfully, False if file not found.
    Called once at server startup.
    """
    global _model, _model_version

    if not MODEL_PATH.exists():
        logger.warning(
            "Model file not found at %s. "
            "Falling back to baseline rule until model is trained.",
            MODEL_PATH,
        )
        return False

    try:
        _model = joblib.load(MODEL_PATH)
        _model_version = MODEL_PATH.stat().st_mtime.__str__()[:10]
        logger.info("ML model loaded from %s (version: %s)", MODEL_PATH, _model_version)
        return True
    except Exception as exc:
        logger.error("Failed to load model: %s", exc)
        _model = None
        return False


def predict(features: dict) -> tuple[int, float, str]:
    """
    Run prediction for a single feature vector.

    Parameters
    ----------
    features : dict  — output of features.extract_features()

    Returns
    -------
    (predicted_label: int, risk_score: float, source: str)
      predicted_label : 1 = high risk, 0 = low risk
      risk_score      : probability of buffering (0.0–1.0)
      source          : "model" or "baseline"
    """
    if _model is None:
        # Model not trained yet — use baseline
        label, score = baseline_module.predict(features.get("buffer_s", 0))
        return label, score, "baseline"

    try:
        # Build DataFrame with named columns so StandardScaler doesn't warn
        X = pd.DataFrame([{col: features.get(col, 0) for col in FEATURE_NAMES}])

        # predict_proba returns [[P(class=0), P(class=1)]]
        proba  = _model.predict_proba(X)[0]
        score  = float(proba[1])   # probability of buffering = class 1
        label  = 1 if score >= PREDICTION_THRESHOLD else 0
        return label, round(score, 4), "model"

    except Exception as exc:
        logger.error("Prediction error: %s", exc)
        # Fallback on any inference error
        label, score = baseline_module.predict(features.get("buffer_s", 0))
        return label, score, "baseline"


def get_model_info() -> dict:
    """Return metadata about the currently loaded model."""
    return {
        "model_loaded": _model is not None,
        "model_version": _model_version,
        "model_path": str(MODEL_PATH),
        "threshold": PREDICTION_THRESHOLD,
        "feature_names": FEATURE_NAMES,
    }
