# TASK-028: Comprehensive Test Suite

## Task ID
TASK-028

## Status
PENDING

## Title
Implement Comprehensive Test Suite

## Description
Build the full test suite for the Zaza MCP server covering unit tests for all tool domains, API client tests, cache tests, utility tests, and MCP protocol integration tests. All tests mock external dependencies — no live API calls.

This task creates the test infrastructure and fills gaps not covered by individual tool task testing requirements.

## Acceptance Criteria

### Functional Requirements
- [ ] `tests/conftest.py` — shared fixtures:
  - Mock `YFinanceClient` with sample data for common tickers (AAPL, MSFT, NVDA, TSLA)
  - Mock `EdgarClient` with sample filing responses
  - Mock `FileCache` (in-memory implementation for tests)
  - Mock `RedditClient` and `StockTwitsClient`
  - Sample OHLCV data generator for TA tests
- [ ] `tests/test_cache.py` — cache hit, miss, expiry, corrupt file, clear
- [ ] `tests/test_api_client.py` — yfinance client caching and error handling
- [ ] `tests/tools/` — per-domain test files:
  - `test_prices.py`, `test_statements.py` — financial data tools
  - `test_ta_moving_averages.py`, `test_ta_momentum.py` — TA tools (at least 2)
  - `test_options_chain.py`, `test_options_greeks.py` — options tools (at least 2)
  - `test_sentiment.py` — sentiment tools including graceful degradation
  - `test_macro.py` — macro tools
  - `test_quantitative.py` — quant tools with seeded RNG determinism
  - `test_institutional.py` — institutional tools
  - `test_earnings.py` — earnings tools
  - `test_backtesting.py` — backtesting with no look-ahead bias verification
  - `test_screener.py` — screener tools with mocked Docker
- [ ] `tests/test_server.py` — MCP protocol integration tests:
  - Server starts and responds to `tools/list`
  - All 66 tools present with valid schemas
  - Sample tool calls return valid JSON
  - Invalid parameters return error responses
- [ ] All tests pass: `uv run pytest tests/`
- [ ] No live API calls — all external dependencies mocked

### Non-Functional Requirements
- [ ] **Performance**: Full test suite runs in < 30 seconds
- [ ] **Coverage**: >80% line coverage across src/zaza/
- [ ] **Determinism**: All tests produce same results on repeated runs (seeded RNG for Monte Carlo)
- [ ] **Isolation**: Tests don't depend on filesystem state, network, or Docker
- [ ] **Documentation**: Each test file has a module docstring explaining what it covers

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance client
- TASK-005: EDGAR client
- TASK-012 through TASK-024: All tool implementations

## Technical Notes

### Shared Fixtures (conftest.py)
```python
import pytest
from unittest.mock import MagicMock
from zaza.cache.store import FileCache

@pytest.fixture
def mock_cache(tmp_path):
    return FileCache(cache_dir=tmp_path)

@pytest.fixture
def sample_ohlcv():
    """Generate deterministic OHLCV data for testing."""
    import pandas as pd
    import numpy as np
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=252, freq="B")
    prices = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, 252)))
    return pd.DataFrame({
        "Open": prices * (1 + rng.uniform(-0.01, 0.01, 252)),
        "High": prices * (1 + rng.uniform(0, 0.02, 252)),
        "Low": prices * (1 - rng.uniform(0, 0.02, 252)),
        "Close": prices,
        "Volume": rng.integers(1_000_000, 10_000_000, 252),
    }, index=dates)

@pytest.fixture
def mock_yf_client(sample_ohlcv):
    client = MagicMock()
    client.get_history.return_value = sample_ohlcv.reset_index().to_dict("records")
    client.get_quote.return_value = {"regularMarketPrice": 150.0, "marketCap": 2_500_000_000_000}
    return client
```

### MCP Protocol Test
```python
import subprocess
import json

def test_server_tools_list():
    """Verify all 66 tools are registered."""
    # Start server, send tools/list request, verify response
    # Use subprocess to start server and communicate over stdin/stdout
```

### Backtesting Anti-Look-Ahead Test
```python
def test_no_look_ahead_bias():
    """Verify signals only use data available at signal time."""
    # Create data with a known pattern
    # Run backtest
    # Verify no signal uses future data
```

### Implementation Hints
1. Use `pytest-asyncio` for async tool tests
2. `tmp_path` fixture is perfect for cache tests (auto-cleanup)
3. The sample OHLCV generator with seed=42 ensures deterministic test data
4. MCP protocol tests may need to communicate via stdin/stdout pipes
5. Group related assertions to minimize test overhead
6. Consider `pytest.mark.slow` for tests that are computationally intensive (Monte Carlo)

## Estimated Complexity
**Large** (12-16 hours)

## References
- ZAZA_ARCHITECTURE.md Section 14 (Testing Strategy)
- CLAUDE.md Build & Development Commands section
