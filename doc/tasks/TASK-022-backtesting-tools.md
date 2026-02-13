# TASK-022: Backtesting & Validation Tools

## Task ID
TASK-022

## Status
PENDING

## Title
Implement Backtesting & Validation Tools (4 Tools)

## Description
Implement 4 backtesting and validation MCP tools: `get_signal_backtest`, `get_strategy_simulation`, `get_prediction_score`, and `get_risk_metrics`. These validate trading signals, simulate strategies, track prediction accuracy, and compute risk-adjusted metrics.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/backtesting/signals.py` — `get_signal_backtest(ticker, signal, lookback_years=5)`:
  - Tests a signal (e.g., "rsi_below_30", "macd_crossover", "golden_cross") on historical data
  - Returns: total signals, win rate at 5d/20d/60d, avg return per signal, best/worst trade, profit factor
  - Supports all signals listed in architecture: RSI, MACD, golden/death cross, Bollinger, volume spike, gap, 52w high/low, custom format
- [ ] `src/zaza/tools/backtesting/simulation.py` — `get_strategy_simulation(ticker, entry_signal, exit_signal, stop_loss_pct=5, take_profit_pct=None)`:
  - Full round-trip strategy simulation; returns total trades, win rate, avg P&L, CAGR, max drawdown, Sharpe, equity curve, vs buy-and-hold
- [ ] `src/zaza/tools/backtesting/scoring.py` — `get_prediction_score(ticker=None)`:
  - Reads prediction log from `~/.zaza/cache/predictions/`; scores past predictions vs actual outcomes
  - Returns: directional accuracy, MAE, bias, confidence calibration
- [ ] `src/zaza/tools/backtesting/risk.py` — `get_risk_metrics(ticker, benchmark="SPY", period="1y")`:
  - Returns: Sharpe, Sortino, max drawdown %, beta, alpha, Treynor, information ratio, VaR/CVaR, Calmar, up/down capture ratio
- [ ] All 4 tools registered via `register_backtesting_tools(app)`
- [ ] Backtest avoids look-ahead bias (strict date-ordered computation)
- [ ] Cache: backtests 24h, risk metrics 4h, prediction scores never cached (always fresh)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests verifying no look-ahead bias; Monte Carlo tests seeded; known-input verification
- [ ] **Performance**: 5-year backtest completes in < 5 seconds
- [ ] **Reliability**: Small sample size flagged when n < 20 signals
- [ ] **Documentation**: Tool descriptions explain limitations (survivorship bias, no transaction costs)

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance client
- TASK-006: MCP server entry point
- TASK-009: Shared TA utilities (for signal generation)
- TASK-010: Shared quantitative model utilities (for risk metrics)

## Technical Notes

### Signal Backtesting Pattern
```python
def backtest_signal(prices, signal_func, holding_periods=[5, 20, 60]):
    signals = signal_func(prices)  # Returns dates where signal fired
    results = []
    for date in signals:
        entry_price = prices.loc[date]
        for period in holding_periods:
            exit_date = date + pd.Timedelta(days=period)
            if exit_date in prices.index:
                exit_price = prices.loc[exit_date]
                ret = (exit_price - entry_price) / entry_price
                results.append({"date": date, "period": period, "return": ret})
    return results
```

### Supported Signals
```python
SIGNAL_REGISTRY = {
    "rsi_below_30": lambda df: df[compute_rsi(df) < 30].index,
    "rsi_above_70": lambda df: df[compute_rsi(df) > 70].index,
    "macd_crossover": lambda df: ...,  # MACD crosses above signal
    "golden_cross": lambda df: ...,    # SMA50 crosses above SMA200
    "death_cross": lambda df: ...,     # SMA50 crosses below SMA200
    "bollinger_lower_touch": lambda df: ...,
    "volume_spike": lambda df: ...,    # volume > 2x 20d avg
    # Custom: "indicator_operator_value" e.g., "rsi_lt_25"
}
```

### Prediction Logging
```python
# When Price Prediction sub-agent makes a prediction, log it:
# ~/.zaza/cache/predictions/AAPL__2025-01-15__30d.json
{
    "ticker": "AAPL",
    "date": "2025-01-15",
    "horizon_days": 30,
    "predicted_range": [180, 195],
    "predicted_direction": "bullish",
    "confidence": 0.72,
    "actual_price": null  // filled in later by get_prediction_score
}
```

### Implementation Hints
1. Look-ahead bias prevention: never use data from after the signal date to compute the signal
2. Profit factor = gross profits / gross losses; > 1.5 is meaningful, < 1.0 means signal loses money
3. Compare every strategy to buy-and-hold — a strategy that underperforms B&H is worse than no strategy
4. Prediction scoring is initially empty — value builds over time as predictions accumulate
5. Flag when n < 20 signals: "Insufficient sample size for statistical significance"

## Estimated Complexity
**Large** (10-14 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.11 (Backtesting & Validation Tools)
