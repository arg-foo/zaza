# Code Review: Pure-Python yfinance Screener

**Date:** 2026-02-23
**Reviewer:** Claude Code (claude-sonnet-4-6)
**Files Reviewed:**
- `src/zaza/config.py`
- `src/zaza/tools/screener/scan_types.py`
- `src/zaza/tools/screener/screener.py`
- `src/zaza/tools/screener/__init__.py`
- `docker-compose.yml`
- `Dockerfile`
- `tests/tools/test_screener.py`
- `tests/test_config.py`

**Test run:** 36/36 pass, 0.68s
**Linting:** ruff reports no violations
**Type checking:** mypy reports no issues

---

## Summary

The implementation is well-structured and follows the established Zaza patterns correctly. The 2-phase screening approach (yfinance pre-filter + TA scoring) is sound in principle, and the code is readable, consistent, and free of command-injection risks. However, there are several actionable issues across correctness, coverage, security, and test quality that must be addressed before this can be considered production-ready.

---

## CRITICAL

### CR-1: `asyncio.Semaphore(0)` Causes Complete Deadlock

**File:** `src/zaza/config.py` line 14

```python
SCREENER_TA_CONCURRENCY = int(os.getenv("SCREENER_TA_CONCURRENCY", "10"))
```

**File:** `src/zaza/tools/screener/screener.py` line 159

```python
semaphore = asyncio.Semaphore(SCREENER_TA_CONCURRENCY)
```

`int()` accepts any integer string, including `"0"` and negative values. If `SCREENER_TA_CONCURRENCY=0` is set in the environment, `asyncio.Semaphore(0)` is created. Every `async with semaphore:` call will then block indefinitely, causing the `screen_stocks` tool to hang until the 30-second `pytest-timeout` kills it. In production, the MCP server would stop responding to screening requests entirely.

**Fix:** Clamp the value to a minimum of 1 in config.py:

```python
SCREENER_TA_CONCURRENCY = max(1, int(os.getenv("SCREENER_TA_CONCURRENCY", "10")))
SCREENER_MAX_CANDIDATES = max(1, int(os.getenv("SCREENER_MAX_CANDIDATES", "250")))
SCREENER_TOP_N = max(1, int(os.getenv("SCREENER_TOP_N", "25")))
```

---

### CR-2: SMA Golden Cross is Dead Code at Runtime

**File:** `src/zaza/tools/screener/scan_types.py` lines 244-251
**File:** `src/zaza/tools/screener/screener.py` line 69

```python
# In _score_symbol:
records = await asyncio.to_thread(
    yf_client.get_history, symbol, period="6mo"
)
```

```python
# In compute_sma (indicators.py) line 53:
if len(df) >= 200:
    # compute golden/death cross
```

A `period="6mo"` request returns approximately 126 trading days. The golden cross / death cross logic in `compute_sma` requires `len(df) >= 200`. This condition can never be true with 6-month history. The `_score_momentum` function awards up to 30 points for a `golden_cross` signal and 20 points for `cross == "above"`, but `cross` is never set in the returned dict with 6-month data, so the `sma.get("cross")` call always returns `None`. The 30-point branch for `golden_cross` in `_score_momentum` is unreachable dead code at runtime.

The same applies to `get_buy_sell_levels` (line 244): `compute_sma(df, periods=[20, 50, 200])` is called, but `sma_200` will always be `None` because `len(df) < 200`.

**Fix:** Use `period="1y"` (approximately 252 trading days) for `_score_symbol` and `get_buy_sell_levels` to enable the golden cross signal. Alternatively, document the limitation and remove the `golden_cross` branch from `_score_momentum` scoring.

---

## HIGH

### HR-1: Coverage Falls Below the 80% Floor

**Requirement from `CLAUDE.md`:** "Coverage floor: 80% (pytest-cov)."

**Actual coverage:**
- `src/zaza/tools/screener/scan_types.py`: 69%
- `src/zaza/tools/screener/screener.py`: 73%
- `src/zaza/tools/screener/__init__.py`: 60%

The following paths are not tested:

| Missing Path | File | Lines |
|---|---|---|
| `_score_symbol` when `len(df) < 20` returns `None` | screener.py | 74-75 |
| `_score_symbol` exception handler | screener.py | 85-87 |
| `get_buy_sell_levels` when `len(df) < 5` | screener.py | 253-257 |
| `get_buy_sell_levels` midpoint adjustment when `buy_upper > sell_lower` | screener.py | 275-278 |
| `register_screener_tools` call path in `__init__.py` | __init__.py | 10-12 |
| Intermediate scoring branches in all 9 scoring functions | scan_types.py | ~130 lines |

**Fix:** Add the following test cases:
1. A test that supplies `history_records` with fewer than 20 rows and asserts the symbol is excluded from results.
2. A test that mocks `yf_client.get_history` to raise an exception and asserts the symbol is silently dropped (not the whole request).
3. A test that supplies `history_records` with 3 rows to `get_buy_sell_levels` and asserts `{"error": ...}` is returned.
4. A test that triggers `buy_upper > sell_lower` and asserts the midpoint adjustment is applied.
5. Tests with hand-crafted DataFrames that exercise the intermediate branches in each scoring function (e.g., `width` between 0.05 and 0.10 for breakout, RSI between 40 and 50 for momentum).

---

### HR-2: Tests Do Not Mock `FileCache` - Writes to `~/.zaza/cache/` During Test Runs

**File:** `tests/tools/test_screener.py`

The following tests call `register(mcp)` which instantiates `FileCache()` with the default `CACHE_DIR = ~/.zaza/cache/`. When `cache.set()` is called after a successful screen result, it writes a `.json` file to the developer's home directory:

- `test_valid_scan_returns_results`
- `test_results_sorted_by_score_descending`
- `test_all_nine_scan_types_accepted` (9 invocations)
- `test_result_shape_has_required_fields`
- All `TestBuySellLevels` tests with `YFinanceClient` mocked

This violates the project testing rule "Mock all external APIs -- no live calls" and the spirit of test isolation. The cache writes are not live API calls, but they do produce side effects on the developer's filesystem.

**Fix:** Use `patch("zaza.tools.screener.screener.FileCache")` in all tests that call `register()`, or add a `tmp_path`-based fixture that sets `ZAZA_CACHE_DIR` to a temporary directory for the duration of the test:

```python
@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ZAZA_CACHE_DIR", str(tmp_path))
    import importlib
    import zaza.config as cfg
    importlib.reload(cfg)
    yield
```

---

### HR-3: `test_buy_below_sell` Uses a Conditional Assert that Can Silently Pass on Error

**File:** `tests/tools/test_screener.py` lines 522-527

```python
if "error" not in result:
    buy_max = result["buy_zone"]["upper"]
    sell_min = result["sell_zone"]["lower"]
    assert buy_max <= sell_min, ...
```

If `get_buy_sell_levels` returns `{"error": ...}` for any reason (including a future regression), this test passes silently without asserting anything. The test is designed to verify a specific invariant; it should not accept error responses.

Additionally, the test does not assert:
- `buy_zone["lower"] <= buy_zone["upper"]`
- `sell_zone["lower"] <= sell_zone["upper"]`

A scenario exists (extreme crash with `buy_upper > sell_upper`) where the midpoint adjustment in screener.py lines 275-278 could push `sell_lower` above `sell_upper`. This is not caught by any assertion.

**Fix:**

```python
async def test_buy_below_sell(self) -> None:
    # ...setup...
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    buy_lower = result["buy_zone"]["lower"]
    buy_upper = result["buy_zone"]["upper"]
    sell_lower = result["sell_zone"]["lower"]
    sell_upper = result["sell_zone"]["upper"]
    assert buy_lower <= buy_upper, "buy_zone lower must be <= upper"
    assert sell_lower <= sell_upper, "sell_zone lower must be <= upper"
    assert buy_upper <= sell_lower, "buy_zone upper must be <= sell_zone lower"
```

---

## MEDIUM

### MR-1: IPO Scan Query Does Not Screen for IPOs

**File:** `src/zaza/tools/screener/scan_types.py` lines 94-100

```python
def _build_ipo_query(exchange_code: str) -> EquityQuery:
    """IPO: market cap < $5B, avg vol > 300k."""
    return EquityQuery("and", [
        EquityQuery("eq", ["exchange", exchange_code]),
        EquityQuery("lt", ["intradaymarketcap", 5_000_000_000]),
        EquityQuery("gt", ["avgdailyvol3m", 300_000]),
    ])
```

This query screens for **small-cap stocks with volume**, not recent IPOs. A company listed in 2005 with a $3B market cap passes this filter. The `yfinance` `EquityQuery` API does not expose a `listingDate` field, so true IPO filtering is not possible through the pre-filter phase.

The scoring function compounds this by relying on `len(df) < 30` from `get_history(period="6mo")` to infer recency. A company that IPO'd 4 years ago but has had a volatile 6 months could return fewer than 30 bars (e.g., if it was suspended). Conversely, a stock that IPO'd 2 months ago will return exactly 40+ bars, not triggering the `very_recent_ipo` branch.

**Fix options:**
1. Rename the scan type to `small_cap` and update the description to be accurate.
2. Document in the description that `ipo` is an approximation using market cap as a proxy and that `yfinance` does not provide listing date filtering.
3. Consider removing the `very_recent_ipo` signal from the scoring function since it cannot be reliably detected via the 6-month history length.

---

### MR-2: Pivot Point Calculation Uses Current (Potentially Unclosed) Bar

**File:** `src/zaza/utils/indicators.py` lines 243-254

```python
def compute_pivot_points(df: pd.DataFrame) -> dict[str, float]:
    h = float(df["High"].iloc[-1])    # last bar's high
    low = float(df["Low"].iloc[-1])   # last bar's low
    c = float(df["Close"].iloc[-1])   # last bar's close
```

Standard pivot point analysis uses the **previous completed period's** High, Low, and Close. Using `iloc[-1]` (the most recent bar) is only valid if that bar is fully closed (end-of-day daily data). With `yfinance` daily history, the last bar may be the current trading day's intraday snapshot if the market is open, meaning High and Low are incomplete. This creates a look-ahead bias in the buy/sell levels for intraday use.

**Fix:** Use `iloc[-2]` for the HLC data when computing pivots (the last *completed* bar):

```python
h = float(df["High"].iloc[-2])
low = float(df["Low"].iloc[-2])
c = float(df["Close"].iloc[-2])
```

Or add a guard to fetch only `period="6mo"` data with `end=yesterday` to ensure the last bar is always closed.

---

### MR-3: Ticker Validation Regex Accepts Non-Ticker Strings

**File:** `src/zaza/tools/screener/screener.py` line 40

```python
_TICKER_PATTERN = re.compile(r"^[A-Za-z0-9.\-]{1,10}$")
```

The pattern accepts strings that are not valid ticker symbols:
- `"123456"` (all digits)
- `".........."` (all dots)
- `"1.2-3.4-5"` (digits only with separators)

While these will not cause a security issue (yfinance will simply return no data for invalid tickers), they bypass the intent of validation. The missing validation is:
- Must start with a letter
- Cannot be composed entirely of non-alpha characters

**Fix:**

```python
_TICKER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]{0,9}$")
```

This requires the first character to be a letter and limits total length to 10.

---

### MR-4: `get_buy_sell_levels` Buy/Sell Zone Logic Can Produce Inverted Sell Zone

**File:** `src/zaza/tools/screener/screener.py` lines 268-278

```python
sell_lower = min(pivots["r1"], fib["level_236"])
sell_upper = max(pivots["r2"], fib["level_0"])

if buy_upper > sell_lower:
    midpoint = (buy_upper + sell_lower) / 2
    buy_upper = round(midpoint - 0.01, 2)
    sell_lower = round(midpoint + 0.01, 2)
```

After the midpoint adjustment, `sell_lower` is updated to `midpoint + 0.01`. However, `sell_upper` is not updated. If `midpoint + 0.01 > sell_upper` (which can happen when the current price is above all historical resistance levels), the resulting `sell_zone` will have `lower > upper`, which is an invalid state.

**Fix:** After the adjustment, re-clamp `sell_upper`:

```python
if buy_upper > sell_lower:
    midpoint = (buy_upper + sell_lower) / 2
    buy_upper = round(midpoint - 0.01, 2)
    sell_lower = round(midpoint + 0.01, 2)
    # Ensure sell zone remains valid after adjustment
    if sell_lower > sell_upper:
        sell_upper = round(sell_lower + (sell_upper - sell_lower + 0.02), 2)
```

Or more simply, derive `sell_upper` after the adjustment:

```python
sell_upper = max(sell_upper, sell_lower + 0.01)
```

---

### MR-5: Missing Config Validation Tests for `SCREENER_TA_CONCURRENCY=0`

**File:** `tests/test_config.py`

The tests `test_screener_default_market_env_override`, `test_screener_default_market_default`, and `test_screener_results_cache_ttl` cover new config additions. However, there are no tests for:
- `SCREENER_MAX_CANDIDATES` env override and default
- `SCREENER_TA_CONCURRENCY` env override and default
- `SCREENER_TOP_N` env override and default
- Boundary behavior (zero or negative values)

Once CR-1 is fixed by clamping, tests should verify the clamping behavior:

```python
def test_screener_ta_concurrency_clamped_to_minimum(monkeypatch):
    monkeypatch.setenv("SCREENER_TA_CONCURRENCY", "0")
    importlib.reload(config_module)
    assert config_module.SCREENER_TA_CONCURRENCY >= 1
```

---

## LOW

### LR-1: `_score_momentum` Comment States Weights Sum to 100 but ADX Weight Is 15 Not 20

**File:** `src/zaza/tools/screener/scan_types.py` line 211

```python
def _score_momentum(df: pd.DataFrame, quote: dict[str, Any]) -> dict[str, Any]:
    """Score momentum candidates.

    Weights: RSI 25, MACD 30, SMA golden cross 30, ADX 15.
    """
```

The comment says `25 + 30 + 30 + 15 = 100`, which is correct. However, when the golden cross is dead code (see CR-2), the effective maximum score with `period="6mo"` data is `25 (RSI) + 30 (MACD) + 20 (sma cross "above") + 15 (ADX) = 90`. If golden cross cannot be triggered, documenting the weights as 30 for SMA is misleading.

**Fix:** After resolving CR-2 by extending the period, this becomes accurate. If the period is not extended, update the comment to reflect the effective maximum.

---

### LR-2: `_score_reversal` Comment Claims 40 pts for Bullish Patterns but Actual Max Is 40

**File:** `src/zaza/tools/screener/scan_types.py` lines 398-413

The docstring says `Weights: ... bullish patterns 40` but the code awards:
- `macd bullish_crossover`: 25 pts
- `macd bullish`: 15 pts
- `hammer_pattern`: 15 pts

Maximum from this category = `25 + 15 = 40` (MACD and hammer are independent). The MACD and hammer checks are separate `if` blocks, so both can trigger simultaneously. Total maximum score = `35 + 25 + 25 + 15 = 100`. The weight comment correctly sums to 100, but calling them "bullish patterns 40" when they are actually two separate indicators (MACD and candlestick) is imprecise.

**Fix:** Update the docstring to clarify:

```python
"""Score reversal candidates.

Weights: RSI oversold 35, stochastic 25, MACD crossover 25, hammer pattern 15.
"""
```

---

### LR-3: `_score_volume` and `_score_bullish` OBV Award Points for Non-Rising OBV

**File:** `src/zaza/tools/screener/scan_types.py` lines 333-334 and 580-581

```python
# _score_volume
if obv.get("obv_trend") == "rising":
    score += 30
    signals.append("obv_rising")
else:
    score += 10  # Awards 10 pts even when OBV is falling
```

```python
# _score_bullish
if obv.get("obv_trend") == "rising":
    score += 15
    signals.append("obv_rising")
else:
    score += 5  # Awards 5 pts even when OBV is falling
```

Awarding points to a bearish OBV divergence contradicts the intent of these scans. A stock with falling OBV receiving 10 points in a volume scan is incorrect — falling OBV signals distribution (selling pressure). This inflates scores for stocks with deteriorating volume patterns.

**Fix:** Remove the `else` branch or award 0 points for falling OBV:

```python
if obv.get("obv_trend") == "rising":
    score += 30
    signals.append("obv_rising")
# else: 0 points for falling OBV
```

Note: In `_score_bearish`, the equivalent logic correctly awards 15 points for *falling* OBV and 5 points for rising OBV. This asymmetry suggests the `else` branches in the bullish/volume scorers are bugs.

---

### LR-4: `register()` Function Creates `FileCache` and `YFinanceClient` Per Registration

**File:** `src/zaza/tools/screener/screener.py` lines 92-93

```python
def register(mcp: FastMCP) -> None:
    cache = FileCache()
    yf_client = YFinanceClient(cache)
```

If `register()` is called multiple times (e.g., in testing), each call creates new `FileCache` and `YFinanceClient` instances. While functionally correct, this makes it harder to inject dependencies for testing without patching at the module level. The pattern used by other tools in this codebase (checking the existing tool patterns) should be confirmed consistent.

This is specifically relevant to tests: each test class creates a new `FastMCP` and calls `register()`, causing `FileCache()` to be instantiated without mocking in most tests (see HR-2).

**Recommendation:** Accept a `cache` and `yf_client` parameter with defaults to enable dependency injection in tests:

```python
def register(
    mcp: FastMCP,
    cache: FileCache | None = None,
    yf_client: YFinanceClient | None = None,
) -> None:
    cache = cache or FileCache()
    yf_client = yf_client or YFinanceClient(cache)
```

---

### LR-5: `get_screening_strategies` Has No Error Handling

**File:** `src/zaza/tools/screener/screener.py` lines 197-208

```python
@mcp.tool()
async def get_screening_strategies() -> str:
    strategies = [
        {"name": cfg.name, "description": cfg.description}
        for cfg in SCAN_TYPES.values()
    ]
    return json.dumps({"strategies": strategies}, default=str)
```

This function has no `try/except` block. All other tools in the file use `try/except Exception`. While the current implementation cannot fail (SCAN_TYPES is a module-level constant), this is inconsistent with the project pattern ("every tool returns `{status, data/error}` -- never unhandled exceptions") and is fragile against future modifications to `SCAN_TYPES`.

**Fix:** Wrap in a `try/except` block:

```python
@mcp.tool()
async def get_screening_strategies() -> str:
    try:
        strategies = [
            {"name": cfg.name, "description": cfg.description}
            for cfg in SCAN_TYPES.values()
        ]
        return json.dumps({"strategies": strategies}, default=str)
    except Exception as e:
        logger.warning("get_screening_strategies_error", error=str(e))
        return json.dumps({"error": str(e)}, default=str)
```

---

### LR-6: History Period Hardcoded, Not Configurable

**File:** `src/zaza/tools/screener/screener.py` lines 69, 244

```python
records = await asyncio.to_thread(
    yf_client.get_history, symbol, period="6mo"
)
```

The `period="6mo"` is hardcoded in both `_score_symbol` and `get_buy_sell_levels`. This limits the depth of TA analysis (see CR-2 for the golden cross impact) and cannot be tuned without code changes. Adding `SCREENER_HISTORY_PERIOD` to config would allow operators to extend the period for deeper analysis.

**Fix:** Add to `src/zaza/config.py`:

```python
SCREENER_HISTORY_PERIOD = os.getenv("SCREENER_HISTORY_PERIOD", "1y")
```

And import and use it in `screener.py`.

---

### LR-7: `test_all_nine_scan_types_accepted` Registers `screen_stocks` Tool Nine Times

**File:** `tests/tools/test_screener.py` lines 235-266

Each loop iteration does:
```python
mcp = FastMCP("test")
register(mcp)
tool = mcp._tool_manager.get_tool("screen_stocks")
```

The `tool` fetch is outside the `with` block but `mcp` and `register` are inside the loop. The code is functionally correct but the pattern of creating a new `FastMCP` + `register` per iteration is wasteful. More importantly, the mcp is created before the patch context managers are entered, so `FileCache` is instantiated unpatched.

This also accesses `mcp._tool_manager` which is a private attribute of the FastMCP SDK. This coupling to internal SDK structure is fragile and can break on SDK version updates.

**Recommendation:** Use the public API if one exists, or add a comment noting this is an internal API dependency.

---

## Infrastructure

### IN-1: `Dockerfile` Stage 4 Dev Image Does Not Copy `tests/conftest.py`

**File:** `Dockerfile` lines 94-103

```dockerfile
FROM runtime AS dev
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra dev
COPY tests/ tests/
CMD ["python", "-m", "pytest", "tests/"]
```

The dev stage copies all of `tests/` which is correct. This is not a blocking issue but is noted as: the `docker-compose.yml` no longer has a `pkscreener` service, and the `Dockerfile` no longer references `docker.io`, which is the correct cleanup. No issues found in the infrastructure changes.

---

## Test Coverage Summary

| Requirement | Status |
|---|---|
| No live API calls | Partial - FileCache writes to disk in 7 tests (HR-2) |
| Seeded RNG for quant tests | Pass - `np.random.seed(42)` used |
| Coverage floor: 80% | Fail - scan_types.py: 69%, screener.py: 73% |
| 30s timeout | Pass - all 36 tests complete in 0.68s |
| All 9 scan types accepted | Pass |
| Error handling on exception | Pass |
| Cache hit path tested | Pass |
| Score bounds 0-100 | Pass - but only for seeded data, not all branches |

---

## Priority Order for Fixes

1. **CR-1** (Semaphore deadlock): Clamp config values to minimum 1.
2. **CR-2** (Dead golden cross code): Change history period to `"1y"`.
3. **HR-1** (Coverage below 80%): Add missing test cases.
4. **HR-2** (FileCache disk writes in tests): Add cache isolation fixture.
5. **HR-3** (Silent assert skip): Remove `if "error" not in result` guard; add intra-zone assertions.
6. **MR-4** (Inverted sell zone): Add sell_upper clamp after midpoint adjustment.
7. **MR-1** (IPO query accuracy): Rename to `small_cap` or document limitation.
8. **LR-3** (OBV false points): Remove `else: score += N` for non-rising OBV in bullish/volume scorers.
9. **MR-5** (Missing config tests): Add tests for three new config constants with boundary cases.
10. **LR-5** (Missing error handling in strategies): Wrap in try/except.
