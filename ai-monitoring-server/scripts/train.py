"""
train.py -- Offline model training script for EdgeStream AI.

Run this AFTER collecting playback data (Phase 6).
This script reads from edgestream.db, labels the data,
trains a Logistic Regression model, evaluates it against
the 2-second buffer baseline, and saves the trained model.

Usage (from ai-monitoring-server/ directory):
    python scripts/train.py

After running, call POST /predict/reload on the AI server
to load the new model without restarting.
"""
import sys
import json
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import MODEL_PATH, BASELINE_BUFFER_THRESHOLD_S
from app.prediction.labeler import label_events_from_db
from app.prediction.features import FEATURE_NAMES
from app.prediction.baseline import predict_batch


def main():
    print("=" * 60)
    print("EdgeStream AI -- Model Training Script")
    print("=" * 60)

    # -- 1. Load and label data -------------------------------------------------
    print("\n[1/5] Loading data from database...")
    df = label_events_from_db()

    if df.empty:
        print("ERROR: No data found in edgestream.db.")
        print("       Run playback sessions first (Phase 6).")
        sys.exit(1)

    print(f"      Total rows:       {len(df)}")
    print(f"      Buffering labels: {df['label'].sum()} ({df['label'].mean()*100:.1f}%)")
    print(f"      Sessions:         {df['session_id'].nunique()}")

    if df['label'].sum() < 20:
        print("\nWARNING: Very few buffering events (<20).")
        print("         Collect more data with throttled network conditions.")
        print("         Proceeding anyway -- results will not be reliable.\n")

    # -- 2. Feature matrix ------------------------------------------------------
    print("\n[2/5] Preparing feature matrix...")
    available_features = [f for f in FEATURE_NAMES if f in df.columns]
    print(f"      Features: {available_features}")

    X = df[available_features].fillna(0)
    y = df["label"]
    groups = df["session_id"]

    # -- 3. Session-aware train/test split --------------------------------------
    # GroupShuffleSplit ensures no session appears in both train and test.
    # This is critical to avoid data leakage between adjacent time windows.
    print("\n[3/5] Splitting data (session-aware)...")
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups))

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    print(f"      Train: {len(X_train)} rows | Test: {len(X_test)} rows")
    print(f"      Train sessions: {df['session_id'].iloc[train_idx].nunique()} | "
          f"Test sessions: {df['session_id'].iloc[test_idx].nunique()}")

    # -- 4. Train Logistic Regression -------------------------------------------
    print("\n[4/5] Training Logistic Regression...")
    lr_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            class_weight="balanced",  # compensate for class imbalance
            max_iter=1000,
            random_state=42,
        )),
    ])
    lr_pipeline.fit(X_train, y_train)

    # -- Optional: also train Random Forest for comparison ---------------------
    print("      Training Random Forest (comparison)...")
    rf_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=100,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])
    rf_pipeline.fit(X_train, y_train)

    # -- 5. Evaluate all three approaches --------------------------------------
    print("\n[5/5] Evaluation Results")
    print("=" * 60)

    y_pred_lr       = lr_pipeline.predict(X_test)
    y_pred_rf       = rf_pipeline.predict(X_test)
    y_pred_baseline = predict_batch(list(X_test["buffer_s"]))

    _print_report("Logistic Regression", y_test, y_pred_lr)
    _print_report("Random Forest",       y_test, y_pred_rf)
    _print_report("Baseline (buffer<2s)", y_test, y_pred_baseline)

    # -- 6. Save the best model (use LR as primary per project spec) ------------
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(lr_pipeline, MODEL_PATH)
    print(f"\nModel saved to: {MODEL_PATH}")
    print("Call POST /predict/reload on the AI server to activate it.")

    # -- 7. Save evaluation summary for the experiments/ folder ----------------
    _save_eval_summary(y_test, y_pred_lr, y_pred_rf, y_pred_baseline,
                       available_features, len(df))


def _print_report(name: str, y_true, y_pred) -> None:
    print(f"\n-- {name} --")
    print(classification_report(y_true, y_pred,
                                 target_names=["No Buffer", "Buffer"],
                                 zero_division=0))
    cm = confusion_matrix(y_true, y_pred)
    print("Confusion Matrix:")
    print(f"  TN={cm[0,0]}  FP={cm[0,1]}")
    print(f"  FN={cm[1,0]}  TP={cm[1,1]}")
    fa_rate = cm[0,1] / max(cm[0,0] + cm[0,1], 1)
    print(f"  False Alarm Rate: {fa_rate:.3f}")


def _save_eval_summary(y_test, y_lr, y_rf, y_base, features, total_rows):
    """Save a JSON summary of evaluation results for the experiments/ folder."""
    out_dir = Path(__file__).parent.parent.parent / "experiments" / "ai_evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "total_rows": total_rows,
        "test_rows": len(y_test),
        "positive_rate": float(y_test.mean()),
        "features": features,
        "results": {
            "logistic_regression": _metrics_dict(y_test, y_lr),
            "random_forest":       _metrics_dict(y_test, y_rf),
            "baseline":            _metrics_dict(y_test, y_base),
        },
    }
    with open(out_dir / "eval_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Evaluation summary saved to {out_dir / 'eval_summary.json'}")


def _metrics_dict(y_true, y_pred) -> dict:
    return {
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall":    round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1":        round(f1_score(y_true, y_pred, zero_division=0), 4),
    }


if __name__ == "__main__":
    main()
