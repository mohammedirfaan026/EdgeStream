"""
evaluate.py -- Compare trained ML model against baseline on the test set.

Run this AFTER scripts/train.py has been executed.
Reads the test data from the labeled CSV, runs both predictors,
and prints a comparison table.

Usage (from experiments/ai_evaluation/ directory):
    python evaluate.py
"""
import sys
import json
from pathlib import Path

# Point to the ai-monitoring-server module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-monitoring-server"))

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from app.config import MODEL_PATH, DATA_DIR, BASELINE_BUFFER_THRESHOLD_S
from app.prediction.features import FEATURE_NAMES
from app.prediction.baseline import predict_batch
from app.prediction.labeler import label_events_from_db
from sklearn.model_selection import GroupShuffleSplit


def main():
    print("=" * 60)
    print("EdgeStream AI -- Model vs Baseline Evaluation")
    print("=" * 60)

    # -- Load labeled data ------------------------------------------------------
    print("\nLoading labeled data from database...")
    df = label_events_from_db()
    if df.empty:
        print("ERROR: No data found. Run playback sessions and export_data.py first.")
        sys.exit(1)

    available = [f for f in FEATURE_NAMES if f in df.columns]
    X = df[available].fillna(0)
    y = df["label"]
    groups = df["session_id"]

    # -- Reproduce same train/test split as train.py ----------------------------
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    _, test_idx = next(gss.split(X, y, groups))
    X_test = X.iloc[test_idx]
    y_test = y.iloc[test_idx]
    print(f"Test set: {len(y_test)} rows | {y_test.sum()} positive ({y_test.mean()*100:.1f}%)")

    # -- Load ML model ----------------------------------------------------------
    if not MODEL_PATH.exists():
        print(f"\nERROR: Model not found at {MODEL_PATH}")
        print("       Run scripts/train.py first.")
        sys.exit(1)

    model = joblib.load(MODEL_PATH)
    print(f"Model loaded: {MODEL_PATH}")

    # -- Predictions ------------------------------------------------------------
    y_pred_lr       = model.predict(X_test)
    y_pred_baseline = predict_batch(list(X_test["buffer_s"]))

    # -- Print comparison -------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"BASELINE RULE: Predict buffer < {BASELINE_BUFFER_THRESHOLD_S}s as HIGH RISK")
    print("=" * 60)
    _print_report("Baseline (buffer<2s)", y_test, y_pred_baseline)

    print("\n" + "=" * 60)
    print("MACHINE LEARNING: Logistic Regression")
    print("=" * 60)
    _print_report("Logistic Regression", y_test, y_pred_lr)

    # -- Summary table ----------------------------------------------------------
    print("\n" + "=" * 60)
    print("COMPARISON TABLE")
    print("=" * 60)
    print(f"{'Metric':<25} {'Baseline':>12} {'LR Model':>12}")
    print("-" * 50)
    for metric_name, fn in [
        ("Precision (buffering)", lambda y, yp: precision_score(y, yp, zero_division=0)),
        ("Recall (buffering)",    lambda y, yp: recall_score(y, yp, zero_division=0)),
        ("F1 (buffering)",        lambda y, yp: f1_score(y, yp, zero_division=0)),
    ]:
        base_val = fn(y_test, y_pred_baseline)
        lr_val   = fn(y_test, y_pred_lr)
        better   = "[WIN]" if lr_val > base_val else ("=" if lr_val == base_val else "[LOSE]")
        print(f"  {metric_name:<23} {base_val:>12.4f} {lr_val:>12.4f}  {better}")

    # -- Save JSON summary ------------------------------------------------------
    out = Path(__file__).parent / "eval_summary.json"
    summary = {
        "test_size": len(y_test),
        "positive_rate": float(y_test.mean()),
        "baseline": _metrics_dict(y_test, y_pred_baseline),
        "logistic_regression": _metrics_dict(y_test, y_pred_lr),
    }
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved -> {out}")
    print("Copy these values into the results.md file.")


def _print_report(name, y_true, y_pred):
    print(f"\n{name}:")
    print(classification_report(y_true, y_pred,
                                  target_names=["No Buffer", "Buffer"],
                                  zero_division=0))
    cm = confusion_matrix(y_true, y_pred)
    print(f"  Confusion Matrix:  TN={cm[0,0]}  FP={cm[0,1]}  FN={cm[1,0]}  TP={cm[1,1]}")
    fa_rate = cm[0,1] / max(cm[0,0] + cm[0,1], 1)
    print(f"  False Alarm Rate:  {fa_rate:.3f}")


def _metrics_dict(y_true, y_pred):
    return {
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall":    round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1":        round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }


if __name__ == "__main__":
    main()
