# AI Evaluation Results

## Setup

- Training data size: [FILL IN] rows
- Test data size: [FILL IN] rows
- Positive rate (buffering events): [FILL IN]%
- Sessions in train: [FILL IN] | Sessions in test: [FILL IN]
- Features used: buffer_s, bitrate_kbps, dl_speed_kbps, dl_time_ms, buffer_trend
- Look-ahead window: 10 seconds
- Date: [FILL IN]

## Baseline Rule

**Rule:** Predict HIGH risk when `buffer_s < 2.0 seconds`

| Metric              | Value |
|---------------------|-------|
| Precision           |       |
| Recall              |       |
| F1-Score            |       |
| False Alarm Rate    |       |
| Confusion Matrix    |       |

## Logistic Regression Model

| Metric              | Value |
|---------------------|-------|
| Precision           |       |
| Recall              |       |
| F1-Score            |       |
| False Alarm Rate    |       |
| Confusion Matrix    |       |

## Comparison Table

| Metric          | Baseline | LR Model | Better? |
|-----------------|----------|----------|---------|
| Precision       |          |          |         |
| Recall          |          |          |         |
| F1-Score        |          |          |         |
| False Alarms    |          |          |         |

## Interpretation

[Write honest interpretation after running evaluate.py]

Example questions to address:
- Does the ML model improve over the baseline?
- On which metric is the improvement most notable?
- Are there conditions where the baseline outperforms the model?
- What is the practical meaning of the false alarm rate?

## Limitations

- Small dataset: results have limited statistical power.
- No cross-validation (single train/test split).
- LAN-only data may not generalise to WAN conditions.
- Model trained and tested on the same video content.
