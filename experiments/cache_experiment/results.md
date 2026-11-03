# Experiment 1: Edge Cache vs Direct Origin — Results
#
# Fill in the results after running run_experiment.ps1
# Do NOT invent numbers — measure them.

## Setup

- Video ID used: `[FILL IN]`
- Segment tested: `seg_00001_360p.ts`
- Trials per condition: 20
- Date: [FILL IN]
- Network: Ethernet LAN

## Raw Results

### Direct Origin (Laptop A :8000)

| Trial | Latency (ms) |
|-------|-------------|
| 1     |             |
| 2     |             |
| ...   |             |

### Via Edge Server (Laptop B :80)

| Trial | Latency (ms) | Cache Status |
|-------|-------------|--------------|
| 1     |             | MISS         |
| 2     |             | HIT          |
| ...   |             |              |

## Computed Metrics

| Metric | Direct Origin | Via Edge (HIT) |
|--------|--------------|----------------|
| p50 latency (ms) | | |
| p95 latency (ms) | | |
| Cache hit ratio | N/A | |

## Cache Hit/Miss Summary

- Total requests via edge: 20
- Cache hits: [FILL IN]
- Cache misses: [FILL IN]  (typically 1 per segment — the first request)
- Hit ratio: [FILL IN]

## Observations

[Write observations after running the experiment]

## Limitations

- This is a same-LAN experiment. The latency improvement shown by cache HITs
  reflects elimination of FastAPI processing overhead on Laptop A, not geographic
  CDN latency reduction. A real CDN benefit comes from geographic proximity.
- Results may vary with segment size and LAN congestion.
