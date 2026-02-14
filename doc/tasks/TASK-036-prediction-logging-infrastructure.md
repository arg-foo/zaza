# TASK-036: Prediction Logging & Self-Scoring Infrastructure

## Task ID
TASK-036

## Status
PENDING

## Title
Build Prediction Logging & Self-Scoring Infrastructure

## Description
Build the filesystem-based prediction logging system that enables Zaza to track its own prediction accuracy over time. When the Prediction sub-agent produces a price forecast, it logs the prediction. The `get_prediction_score` tool reads these logs and compares predictions against actual outcomes, computing directional accuracy, MAE, and bias.

This is actual Python code in the Zaza MCP server, not CLAUDE.md behavioral instructions.

## Acceptance Criteria

### Functional Requirements
- [ ] Prediction log storage at `~/.zaza/predictions/` directory
- [ ] Each prediction stored as a JSON file with naming convention: `{ticker}_{date}_{horizon}.json`
- [ ] Prediction log schema includes:
  - `ticker`: Stock symbol
  - `prediction_date`: When the prediction was made (ISO 8601)
  - `horizon_days`: Forecast horizon (e.g., 30)
  - `target_date`: prediction_date + horizon_days
  - `current_price`: Price at time of prediction
  - `predicted_range`: {low, mid, high} price targets
  - `confidence_interval`: {ci_5, ci_25, ci_75, ci_95} percentiles
  - `model_weights`: Which signals were weighted and how
  - `key_factors`: Top 3-5 factors driving the prediction
  - `actual_price`: Filled in later when scoring (null initially)
  - `scored`: Boolean, false initially
- [ ] `log_prediction()` utility function that the Prediction sub-agent workflow references
- [ ] `score_predictions()` function used by `get_prediction_score` tool:
  - Reads all prediction files (optionally filtered by ticker)
  - For predictions past their target_date, fetches actual price via yfinance
  - Computes: directional accuracy, MAE, MAPE, bias (consistently over/under)
  - Updates `actual_price` and `scored` fields
  - Returns aggregate and per-prediction scores
- [ ] Log rotation: archive predictions older than 1 year to `~/.zaza/predictions/archive/`
- [ ] Handles concurrent writes safely (file-level locking or atomic writes)

### Non-Functional Requirements
- [ ] Uses orjson for serialization (consistent with project patterns)
- [ ] No external database — pure filesystem (JSON files)
- [ ] Prediction log files are human-readable (pretty-printed JSON)
- [ ] Graceful handling of missing/corrupt log files
- [ ] Unit tests with mocked filesystem and yfinance calls

## Dependencies
- TASK-002: Configuration Module (for paths, config)
- TASK-004: yfinance API Client (for fetching actual prices when scoring)
- TASK-022: Backtesting & Validation Tools (get_prediction_score tool implementation)

## Technical Notes

### File Structure
```
~/.zaza/predictions/
├── AAPL_2024-01-15_30d.json
├── NVDA_2024-01-20_30d.json
├── TSLA_2024-02-01_14d.json
└── archive/
    └── (predictions older than 1 year)
```

### Integration Points
1. **Prediction Sub-Agent** (TASK-035): After synthesizing a prediction, the sub-agent calls the log_prediction utility. This is referenced in the CLAUDE.md prompt template.
2. **get_prediction_score Tool** (TASK-022): Calls score_predictions() to read and evaluate the log.
3. **Config Module** (TASK-002): Prediction log directory path should be configurable.

### Implementation Hints
1. Place logging utilities in `src/zaza/utils/predictions.py` or `src/zaza/predictions/`
2. Use `orjson.dumps(data, option=orjson.OPT_INDENT_2)` for human-readable output
3. For atomic writes: write to temp file, then rename (prevents corrupt files)
4. `score_predictions()` should cache actual prices to avoid redundant yfinance calls when scoring multiple predictions for the same ticker
5. Consider a simple `PredictionLog` dataclass or Pydantic model for the schema

### Scoring Metrics
- **Directional accuracy**: Did the prediction get the direction (up/down) right?
- **MAE**: Mean Absolute Error of mid-point prediction vs. actual
- **MAPE**: Mean Absolute Percentage Error
- **Bias**: Average signed error (positive = consistently bullish, negative = bearish)
- **Range accuracy**: Did actual price fall within predicted confidence interval?

## Estimated Complexity
**Small** (2-3 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7 (get_prediction_score tool description)
- ZAZA_ARCHITECTURE.md Section 6.2 (Prediction Sub-Agent workflow)
