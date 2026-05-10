# Model files

`bot_detector_bundle.joblib` contains the trained model, feature columns, thresholds and model name.

Expected bundle format:

```python
{
    "model": trained_model,
    "feature_cols": [...],
    "thresholds": {"allow_max": 0.30, "captcha_max": 0.70},
    "model_name": "RandomForest"
}
```

The FastAPI backend loads this file and applies the same feature order during `/api/risk-score`.
