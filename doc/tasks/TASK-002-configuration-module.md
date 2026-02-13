# TASK-002: Configuration Module

## Task ID
TASK-002

## Status
PENDING

## Title
Implement Configuration Module

## Description
Implement `src/zaza/config.py` to centralize all environment variables, constants, and API key management. This module is imported by every API client and tool module — it provides a single source of truth for configuration.

The module must support graceful degradation: core tools (yfinance, SEC EDGAR) require no keys, while optional tools (Reddit sentiment, FRED economic calendar) check for keys and disable gracefully when absent.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/config.py` implemented
- [ ] Loads environment variables from `.env` file (if present) and from system environment
- [ ] Exposes constants: cache directory (`~/.zaza/cache/`), prediction log directory (`~/.zaza/cache/predictions/`)
- [ ] Exposes API key accessors: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `FRED_API_KEY`
- [ ] Provides `has_reddit_credentials() -> bool` and `has_fred_key() -> bool` helper functions
- [ ] Exposes cache TTL constants for all 23 data categories (prices: 1h, options: 30m, fundamentals: 24h, etc.)
- [ ] Exposes SEC EDGAR User-Agent header string
- [ ] Creates cache directories on import if they don't exist
- [ ] Exposes PKScreener Docker container name constant (`pkscreener`)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests for config loading, missing keys, directory creation
- [ ] **Security**: No API keys in source code; all from environment variables
- [ ] **Documentation**: Docstrings for all public functions and constants

## Dependencies
- TASK-001: Project scaffolding (package structure must exist)

## Technical Notes

### Cache TTL Constants (seconds)
```python
CACHE_TTL = {
    "prices": 3600,          # 1 hour
    "fundamentals": 86400,   # 24 hours
    "filings_meta": 86400,   # 24 hours
    "company_facts": 604800, # 7 days
    "options_chain": 1800,   # 30 minutes
    "implied_vol": 1800,     # 30 minutes
    "news_sentiment": 7200,  # 2 hours
    "social_sentiment": 3600,# 1 hour
    "insider_sentiment": 86400,
    "fear_greed": 14400,     # 4 hours
    "treasury_yields": 3600,
    "market_indices": 3600,
    "commodities": 3600,
    "economic_calendar": 86400,
    "correlations": 21600,   # 6 hours
    "short_interest": 86400,
    "institutional_holdings": 604800,
    "fund_flows": 86400,
    "dark_pool": 86400,
    "earnings_history": 604800,
    "earnings_calendar": 86400,
    "event_calendar": 86400,
    "buyback_data": 604800,
    "quant_models": 14400,
    "backtest_results": 86400,
    "risk_metrics": 14400,
}
```

### Implementation Pattern
```python
import os
from pathlib import Path

CACHE_DIR = Path.home() / ".zaza" / "cache"
PREDICTIONS_DIR = CACHE_DIR / "predictions"
PKSCREENER_CONTAINER = "pkscreener"
EDGAR_USER_AGENT = "Zaza/1.0 (contact@example.com)"

def _ensure_dirs():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

_ensure_dirs()

def has_reddit_credentials() -> bool:
    return bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"))

def has_fred_key() -> bool:
    return bool(os.getenv("FRED_API_KEY"))
```

### Implementation Hints
1. Use `os.getenv()` for all key access — never raise on missing optional keys
2. Call `_ensure_dirs()` at module import time so cache directories exist before any tool runs
3. Consider using `python-dotenv` for `.env` file loading, but keep it optional (don't fail if not installed)

## Estimated Complexity
**Small** (1-2 hours)

## References
- ZAZA_ARCHITECTURE.md Section 9.2 (File-Based Response Cache)
- ZAZA_ARCHITECTURE.md Section 13 (Configuration & Setup)
