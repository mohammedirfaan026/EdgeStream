"""
baseline.py — Simple rule-based buffering prediction baseline.

Used to compare against the trained ML model.

Rule: predict buffering risk when current buffer duration < BASELINE_BUFFER_THRESHOLD_S

This is the simplest possible predictor — it requires no training data
and produces a hard binary prediction (not a probability).

The purpose of comparing against this baseline is to determine whether
the trained ML model provides measurable value over such a simple heuristic.
"""
from app.config import BASELINE_BUFFER_THRESHOLD_S


def predict(buffer_s: float) -> tuple[int, float]:
    """
    Return (predicted_label, risk_score).

    predicted_label: 1 = buffering likely, 0 = no risk
    risk_score:      1.0 if buffer below threshold, 0.0 otherwise
                     (no probabilistic output — it's a hard rule)
    """
    if buffer_s < BASELINE_BUFFER_THRESHOLD_S:
        return 1, 1.0
    return 0, 0.0


def predict_batch(buffer_values: list[float]) -> list[int]:
    """Apply the baseline rule to a list of buffer values. Used in evaluate.py."""
    return [1 if b < BASELINE_BUFFER_THRESHOLD_S else 0 for b in buffer_values]
