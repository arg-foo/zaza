# TASK-019: Quantitative Model Tools

## Task ID
TASK-019

## Status
PENDING

## Title
Implement Quantitative Model Tools (6 Tools)

## Description
Implement 6 quantitative modeling MCP tools: `get_price_forecast`, `get_volatility_forecast`, `get_monte_carlo_simulation`, `get_return_distribution`, `get_mean_reversion`, and `get_regime_detection`. Pure computation on historical OHLCV data using statsmodels, arch, scipy, and numpy.

These form the statistical backbone of the Price Prediction sub-agent.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/quantitative/forecast.py` — `get_price_forecast(ticker, horizon_days=30, model="arima")`:
  - ARIMA with auto order selection OR Prophet; returns daily point forecast, 80%/95% confidence intervals, model fit metrics
- [ ] `src/zaza/tools/quantitative/volatility.py` — `get_volatility_forecast(ticker, horizon_days=30)`:
  - GARCH(1,1); returns daily vol forecast, annualized vol, vol regime classification, 1-day/5-day VaR
- [ ] `src/zaza/tools/quantitative/monte_carlo.py` — `get_monte_carlo_simulation(ticker, horizon_days=30, simulations=10000)`:
  - GBM; returns probability cone (5th/25th/50th/75th/95th percentile paths), probability of ±5%/±10%/±20%
- [ ] `src/zaza/tools/quantitative/distribution.py` — `get_return_distribution(ticker, period="1y")`:
  - Returns mean, std, skewness, kurtosis, fat tail analysis, VaR/CVaR, max drawdown, Jarque-Bera test
- [ ] `src/zaza/tools/quantitative/mean_reversion.py` — `get_mean_reversion(ticker)`:
  - Z-score vs 20/50/200-day MA, half-life (Ornstein-Uhlenbeck), Hurst exponent, mean reversion probability
- [ ] `src/zaza/tools/quantitative/regime.py` — `get_regime_detection(ticker)`:
  - Current regime (trending-up/trending-down/range-bound/high-volatility), confidence, duration, historical frequencies
- [ ] All 6 tools registered via `register_quantitative_tools(app)`
- [ ] Cached with "quant_models" category (4h TTL)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with known data for deterministic outputs; Monte Carlo uses seeded RNG; verify ARIMA, GARCH convergence
- [ ] **Performance**: Model fitting < 5 seconds for 5 years of daily data; Monte Carlo (10k sims) < 3 seconds
- [ ] **Reliability**: Fallback to simpler models when fitting fails (ARIMA(1,1,1) as default)
- [ ] **Documentation**: Tool descriptions explain model assumptions and limitations

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance client
- TASK-006: MCP server entry point
- TASK-010: Shared quantitative model utilities

## Technical Notes

### Prophet Integration
```python
from prophet import Prophet
import pandas as pd

def forecast_with_prophet(prices, horizon_days):
    df = pd.DataFrame({"ds": prices.index, "y": prices.values})
    model = Prophet(daily_seasonality=False, weekly_seasonality=True)
    model.fit(df)
    future = model.make_future_dataframe(periods=horizon_days)
    forecast = model.predict(future)
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(horizon_days)
```

### Vol Regime Classification
```python
# Low: current vol < 25th percentile of 1Y history
# Normal: 25th-75th percentile
# High: 75th-95th percentile
# Extreme: > 95th percentile
```

### Implementation Hints
1. ARIMA auto-selection is the slowest part — cache model parameters after first fit
2. GARCH requires `returns * 100` scaling for the `arch` library
3. Monte Carlo: use `np.random.default_rng(seed)` for test reproducibility
4. Prophet suppresses stdout by default but may produce warnings — redirect to logger
5. Hurst exponent near 0.5 means random walk — mean reversion analysis is less reliable
6. All tools fetch OHLCV data internally via yfinance client + cache

## Estimated Complexity
**Large** (10-14 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.8 (Quantitative Models Tools)
