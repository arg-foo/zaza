# TASK-009: Shared TA Computation Utilities

## Task ID
TASK-009

## Status
COMPLETED

## Title
Implement Shared TA Computation Utilities

## Description
Implement `src/zaza/utils/indicators.py` — shared technical analysis computation helpers used by all 9 TA tools. This module wraps the `ta` library and `pandas` to provide consistent indicator computation from OHLCV data.

Each TA tool follows the same pattern: fetch OHLCV → convert to DataFrame → compute indicators → return structured JSON. This utility module centralizes the DataFrame conversion and common indicator computations.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/utils/indicators.py` implemented
- [ ] `ohlcv_to_dataframe(data: list[dict]) -> pd.DataFrame` — converts OHLCV list to DataFrame with proper column names (Open, High, Low, Close, Volume)
- [ ] `compute_sma(df: pd.DataFrame, periods: list[int]) -> dict` — Simple Moving Averages
- [ ] `compute_ema(df: pd.DataFrame, periods: list[int]) -> dict` — Exponential Moving Averages
- [ ] `compute_rsi(df: pd.DataFrame, period: int = 14) -> dict` — RSI with signal classification
- [ ] `compute_macd(df: pd.DataFrame) -> dict` — MACD(12,26,9) with signal and histogram
- [ ] `compute_stochastic(df: pd.DataFrame) -> dict` — Stochastic %K/%D
- [ ] `compute_bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> dict` — Bollinger Bands
- [ ] `compute_atr(df: pd.DataFrame, period: int = 14) -> float` — Average True Range
- [ ] `compute_adx(df: pd.DataFrame, period: int = 14) -> dict` — ADX with +DI/-DI
- [ ] `compute_obv(df: pd.DataFrame) -> dict` — On-Balance Volume with trend
- [ ] `compute_vwap(df: pd.DataFrame) -> float` — Volume Weighted Average Price
- [ ] `compute_cmf(df: pd.DataFrame, period: int = 20) -> float` — Chaikin Money Flow
- [ ] `compute_mfi(df: pd.DataFrame, period: int = 14) -> dict` — Money Flow Index
- [ ] `compute_ichimoku(df: pd.DataFrame) -> dict` — Ichimoku Cloud components
- [ ] `compute_pivot_points(df: pd.DataFrame) -> dict` — Standard pivot points with S/R levels
- [ ] `compute_fibonacci_levels(high: float, low: float) -> dict` — Fibonacci retracement levels (23.6%, 38.2%, 50%, 61.8%)
- [ ] All functions return latest values + pre-computed signal summaries (e.g., "bullish", "overbought")

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with known OHLCV data verifying exact indicator values
- [ ] **Performance**: Efficient pandas operations — no row-by-row iteration
- [ ] **Documentation**: Docstrings explaining each indicator and its signal interpretation

## Dependencies
- TASK-001: Project scaffolding

## Technical Notes

### Signal Classification Pattern
Every indicator computation returns both the raw value and a signal interpretation:
```python
def compute_rsi(df: pd.DataFrame, period: int = 14) -> dict:
    rsi = ta.momentum.RSIIndicator(df["Close"], window=period).rsi()
    value = round(rsi.iloc[-1], 2)
    if value > 70:
        signal = "overbought"
    elif value > 60:
        signal = "approaching overbought"
    elif value < 30:
        signal = "oversold"
    elif value < 40:
        signal = "approaching oversold"
    else:
        signal = "neutral"
    return {"rsi_14": value, "signal": signal}
```

### OHLCV DataFrame Convention
All TA utilities expect a DataFrame with columns: `Open`, `High`, `Low`, `Close`, `Volume` (capitalized, matching yfinance convention).

### Implementation Hints
1. Use the `ta` library for most computations — it's well-tested and handles edge cases
2. For Ichimoku, `ta.trend.IchimokuIndicator` computes all components
3. Fibonacci levels are pure math: `high - (high - low) * ratio` for each ratio
4. Always use `.iloc[-1]` to get the most recent value
5. Handle NaN values (insufficient data) by returning None for those indicators

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 8 (Technical Analysis Sub-Tools)
- ta library: https://technical-analysis-library-in-python.readthedocs.io/
