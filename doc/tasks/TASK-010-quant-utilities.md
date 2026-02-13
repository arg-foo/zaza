# TASK-010: Shared Quantitative Model Utilities

## Task ID
TASK-010

## Status
PENDING

## Title
Implement Shared Quantitative Model Utilities

## Description
Implement `src/zaza/utils/models.py` — shared statistical and quantitative model helpers used by the 6 quantitative tools and 4 backtesting tools. This module wraps `statsmodels`, `scipy`, `numpy`, and `arch` for ARIMA fitting, GARCH estimation, Monte Carlo simulation, distribution analysis, and Hurst exponent computation.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/utils/models.py` implemented
- [ ] `fit_arima(returns: np.ndarray, order: tuple = None) -> dict` — ARIMA model with automatic order selection (AIC minimization), fallback to (1,1,1)
- [ ] `fit_garch(returns: np.ndarray) -> dict` — GARCH(1,1) fit with forecasted volatility
- [ ] `monte_carlo_gbm(price: float, mu: float, sigma: float, days: int, n_sims: int = 10000, seed: int = None) -> dict` — Geometric Brownian Motion simulation returning percentile paths
- [ ] `compute_hurst_exponent(prices: np.ndarray) -> float` — Rescaled range (R/S) analysis
- [ ] `compute_half_life(prices: np.ndarray) -> float` — Ornstein-Uhlenbeck half-life of mean reversion
- [ ] `compute_return_stats(returns: np.ndarray) -> dict` — mean, std, skewness, kurtosis, Jarque-Bera test
- [ ] `compute_var(returns: np.ndarray, confidence: float = 0.95) -> dict` — Value at Risk (parametric and historical)
- [ ] `compute_cvar(returns: np.ndarray, confidence: float = 0.95) -> float` — Conditional VaR (Expected Shortfall)
- [ ] `classify_regime(prices: np.ndarray, returns: np.ndarray) -> dict` — regime classification using vol percentile + trend direction + ADX
- [ ] All functions accept numpy arrays and return dicts/floats

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with known inputs verifying deterministic outputs; Monte Carlo tests use seeded RNG
- [ ] **Performance**: Model fitting should complete in <5 seconds for 5 years of daily data
- [ ] **Reliability**: Graceful fallback when model fitting fails (e.g., ARIMA convergence issues)
- [ ] **Documentation**: Docstrings explaining model assumptions and limitations

## Dependencies
- TASK-001: Project scaffolding

## Technical Notes

### ARIMA Auto-Selection
```python
from statsmodels.tsa.arima.model import ARIMA
import itertools

def fit_arima(returns, order=None):
    if order:
        model = ARIMA(returns, order=order).fit()
    else:
        best_aic, best_order = float("inf"), (1,1,1)
        for p, d, q in itertools.product(range(3), range(2), range(3)):
            try:
                m = ARIMA(returns, order=(p,d,q)).fit()
                if m.aic < best_aic:
                    best_aic, best_order = m.aic, (p,d,q)
            except:
                continue
        model = ARIMA(returns, order=best_order).fit()
    return {"order": model.specification["order"], "aic": model.aic, "forecast": ...}
```

### GARCH Volatility
```python
from arch import arch_model

def fit_garch(returns):
    model = arch_model(returns * 100, vol="Garch", p=1, q=1)
    result = model.fit(disp="off")
    forecast = result.forecast(horizon=30)
    return {"params": ..., "forecasted_vol": ...}
```

### Monte Carlo (GBM)
```python
def monte_carlo_gbm(price, mu, sigma, days, n_sims=10000, seed=None):
    rng = np.random.default_rng(seed)
    dt = 1/252
    paths = np.zeros((n_sims, days))
    paths[:, 0] = price
    for t in range(1, days):
        z = rng.standard_normal(n_sims)
        paths[:, t] = paths[:, t-1] * np.exp((mu - 0.5*sigma**2)*dt + sigma*np.sqrt(dt)*z)
    percentiles = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
    return {"percentiles": percentiles, "paths": paths}
```

### Implementation Hints
1. ARIMA auto-selection can be slow — limit the search space to (p<3, d<2, q<3)
2. GARCH fitting may fail on very short series — require at least 252 data points
3. Use `np.random.default_rng(seed)` for reproducible Monte Carlo results
4. Hurst exponent: H < 0.5 = mean-reverting, H > 0.5 = trending, H ≈ 0.5 = random walk

## Estimated Complexity
**Medium** (6-8 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.8 (Quantitative Models Tools)
- statsmodels ARIMA: https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html
- arch library: https://arch.readthedocs.io/
