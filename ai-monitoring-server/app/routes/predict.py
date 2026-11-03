"""
predict.py — Endpoints for model management and prediction status.

These are used by:
  - The dashboard (to show model info and evaluation metrics).
  - The admin operator (to trigger model retraining).
"""
from fastapi import APIRouter
from app.prediction import model as model_module

router = APIRouter(prefix="/predict", tags=["prediction"])


@router.get("/status")
def prediction_status() -> dict:
    """
    Return current model status.
    Shows whether a trained model is loaded or we're using the fallback baseline.
    """
    return model_module.get_model_info()


@router.post("/reload")
def reload_model() -> dict:
    """
    Reload the model from disk without restarting the server.
    Call this after running scripts/train.py to deploy the new model.
    """
    success = model_module.load_model()
    return {
        "success": success,
        "message": "Model reloaded from disk." if success
                   else "Model file not found. Run scripts/train.py first.",
        **model_module.get_model_info(),
    }
