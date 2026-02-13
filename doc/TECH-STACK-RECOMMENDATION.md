# Zaza Tech Stack Recommendation

## Executive Summary

This document provides a comprehensive tech stack evaluation for Zaza, a financial research MCP server with 66 tools across 11 domains. The analysis covers every layer of the system: runtime, MCP framework, package management, data access, computation, HTTP/scraping, browser automation, Docker integration, testing, linting, serialization, logging, and resilience. Each recommendation is backed by current ecosystem research and evaluated against the specific constraints of an MCP server that communicates over stdin/stdout with Claude Code.

The overall finding: the architecture document's dependency choices are largely sound, with targeted upgrades recommended in caching (diskcache over raw file JSON), serialization (orjson for hot paths), resilience (tenacity for retries), logging (structlog), and testing (respx + pytest-cov). The pandas vs. polars decision and the `ta` library choice warrant the most careful consideration.

---

## 1. Core Runtime and Language

### Recommendation: Python 3.12+

**Why:** Python 3.12 introduced significant performance improvements (faster startup, optimized comprehensions, improved error messages) and is the minimum version already specified in the architecture. Python 3.13 is now stable with further performance gains from the experimental free-threaded mode, but 3.12 remains the safer minimum floor given dependency compatibility.

**Specific guidance:**
- Set `requires-python = ">=3.12"` in pyproject.toml (already planned).
- Target 3.12 for CI testing. Optionally test 3.13 as a matrix entry.
- Do NOT target 3.14 yet; several scientific dependencies (statsmodels, arch, prophet) lag on bleeding-edge CPython support.

**Async framework:** The MCP server uses `asyncio` natively (the `mcp` SDK is async). No additional async framework (Trio, AnyIO) is needed. The MCP SDK handles the event loop. Playwright uses its own async API that integrates with asyncio. The `subprocess`-based Docker exec calls are synchronous but should be wrapped with `asyncio.to_thread()` to avoid blocking the event loop.

**Alternatives considered:**
- Python 3.13: Free-threaded mode is experimental and most C-extension libraries (numpy, pandas) have not validated thread safety. Not worth the risk for a v0.1.
- Python 3.11: No reason to go lower. 3.12 has better error messages and performance.

**Risks:** Prophet's dependency on `cmdstanpy` / `pystan` can be sensitive to CPython minor version. Pin prophet version and test installation on target Python version before committing.

---

## 2. MCP Server Framework

### Recommendation: Official MCP Python SDK (`mcp` package)

**Current version:** 1.26.0 (February 2026)
**GitHub:** [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
**PyPI:** [mcp](https://pypi.org/project/mcp/)

**Why:** The official SDK is the canonical choice for Claude Code integration. It implements the full MCP specification including stdio transport, tool registration, and schema generation. FastMCP 1.0's core was merged into the official SDK, so `from mcp.server.fastmcp import FastMCP` is available within the official package.

**Specific guidance:**
- Use `FastMCP` from within the official SDK for the higher-level decorator-based API (cleaner tool registration than the low-level `Server` class).
- Pin: `mcp>=1.20,<2.0` to stay on the current major version.

```python
# Recommended: use FastMCP from within the official SDK
from mcp.server.fastmcp import FastMCP

app = FastMCP("zaza")

@app.tool()
async def get_price_snapshot(ticker: str) -> dict:
    """Get current price snapshot for a ticker."""
    ...
```

**Alternative considered:**
- Standalone FastMCP 2.x/3.x ([jlowin/fastmcp](https://github.com/jlowin/fastmcp)): Adds server composition, proxying, OpenAPI generation, and auth. These features are not needed for Zaza since Claude Code is the sole client and there is no auth requirement. Using the standalone package adds a dependency that may diverge from the official spec. Not justified for this use case.

**Risks:** The MCP spec is still evolving. Pin to a known-good version range and test after upgrades. The `FastMCP` sub-module within the official SDK may lag behind the standalone project's features, but for tool registration and stdio transport, it is sufficient.

---

## 3. Package Management

### Recommendation: uv (confirmed)

**Current version:** 0.10.2 (February 2026)
**GitHub:** [astral-sh/uv](https://github.com/astral-sh/uv)
**Docs:** [docs.astral.sh/uv](https://docs.astral.sh/uv/)

**Why:** uv is 10-100x faster than pip/pip-tools, provides deterministic lockfiles (`uv.lock`), manages Python versions, and has become the de facto standard for modern Python projects. It is written in Rust with excellent reliability. The architecture already specifies uv, and this is the correct choice.

**Specific guidance:**
- Use `uv sync` for dependency installation.
- Use `uv run` for all script execution (ensures virtual environment).
- Commit `uv.lock` to version control for reproducible builds.
- Use `uv python install 3.12` to pin the Python version for contributors.

**Alternatives considered:**
- Poetry: Slower resolution, heavier, and losing momentum to uv. Not recommended.
- pip + pip-tools: Manual, slower, no Python version management. Superseded by uv.
- PDM: Capable but smaller community. uv has won the ecosystem.

**Risks:** uv is pre-1.0 (0.10.x), meaning breaking changes are possible but have been rare and well-communicated. The Astral team (also behind Ruff) has a strong track record of backward compatibility.

---

## 4. Data Layer

### 4.1 Market Data Client

#### Recommendation: yfinance (confirmed, with caveats)

**Current version:** 1.0 (January 2026)
**GitHub:** [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) (21.4k stars)
**PyPI:** [yfinance](https://pypi.org/project/yfinance/)

**Why:** yfinance is the only free, no-API-key library that covers the breadth Zaza needs: OHLCV prices, fundamentals, options chains, institutional holders, insider trades, analyst estimates, earnings, and news. It powers 35+ of Zaza's 66 tools. No alternative matches this breadth at zero cost.

**Known risks (critical):**
- yfinance scrapes Yahoo Finance's undocumented backend. Yahoo periodically changes its API structure, which breaks yfinance. This has happened multiple times historically.
- Rate limiting: aggressive scraping can trigger IP blocks.
- Data is delayed (15-20 min for options, end-of-day for fundamentals).
- No SLA, no support contract, no uptime guarantee.

**Mitigation strategy:**
1. **Cache aggressively** (already planned): 30min for options, 1hr for prices, 24hr for fundamentals, 7d for company facts.
2. **Pin yfinance version** and test before upgrading. Do not use `>=` with no upper bound.
3. **Wrap all yfinance calls in try/except with graceful degradation.** A broken yfinance call should return an error message, not crash the MCP server.
4. **Design the API client layer with an abstraction boundary** (`src/zaza/api/yfinance_client.py`) so yfinance can be swapped for a paid API (Alpha Vantage, Polygon.io) in the future without changing tool implementations. This is one place where an abstraction is justified because the underlying data source is fragile and likely to need replacement.

**Alternatives evaluated and rejected (for v0.1):**
| Alternative | Cost | Why Rejected |
|------------|------|-------------|
| Alpha Vantage | Free tier: 25 req/day | Too restrictive for 35+ tools |
| Polygon.io | $29/mo starter | Paid; premature for a v0.1 research project |
| IEX Cloud | Pay-per-use | Paid; options data requires higher tiers |
| Tiingo | Free tier: 500 req/hr | Missing options chains, insider trades |
| EODHD | Free tier limited | Missing several data categories |

**Recommended pin:** `yfinance>=1.0,<2.0`

#### 4.2 SEC EDGAR Client

#### Recommendation: httpx (direct HTTP calls)

No wrapper library needed. The SEC EDGAR API is a straightforward REST API with JSON responses. Use httpx directly with the required `User-Agent` header. The architecture's plan to build `edgar_client.py` as a thin httpx wrapper is correct.

**Specific guidance:**
- Set `User-Agent` to `"Zaza/0.1 (your-email@example.com)"` per SEC EDGAR requirements.
- Rate limit to 10 requests/second (SEC's published limit).
- Cache filing metadata for 24hr, company facts for 7d.

#### 4.3 Social and Macro API Clients

| Client | Library | Notes |
|--------|---------|-------|
| Reddit | `praw>=7.7` | Official Reddit API wrapper. Requires free API key registration. Well-maintained. |
| StockTwits | `httpx` (direct) | No official SDK. Simple REST API, use httpx directly. |
| FRED | `httpx` (direct) | Simple REST API. Alternatively, `fredapi` package exists but is a thin wrapper that adds no value over httpx. |
| CNN Fear & Greed | `httpx` + `beautifulsoup4` | Web scrape. Fragile by nature. |
| FINRA ADF | `httpx` + `beautifulsoup4` | Web scrape. Fragile by nature. |

**Pin:** `praw>=7.7,<8.0`

### 4.4 Caching

#### Recommendation: diskcache (upgrade from raw file-based JSON)

**GitHub:** [grantjenks/python-diskcache](https://github.com/grantjenks/python-diskcache)
**PyPI:** [diskcache](https://pypi.org/project/diskcache/)

**Why the current plan has issues:** The architecture specifies a custom `FileCache` class that writes individual JSON files to `~/.zaza/cache/`. This works for a prototype but has problems at scale:
- No atomic writes (concurrent tool calls can corrupt files)
- No eviction policy (cache grows unbounded)
- No tag-based invalidation
- No built-in concurrency safety

**Why diskcache is better:**
- SQLite-backed with ACID guarantees and thread/process safety
- Built-in TTL support via `expire` parameter on `set()`
- Tag-based eviction (clear all "prices" entries without touching "fundamentals")
- FanoutCache for concurrent write performance
- `Cache` object implements `dict`-like interface: `cache[key] = value`
- 1.5k GitHub stars, actively maintained, pure Python, Apache 2.0 license
- Proven in production at scale since 2016

**Migration path:**
```python
# Before (custom FileCache)
cache = FileCache(CACHE_DIR)
data = cache.get(key, "prices")

# After (diskcache)
from diskcache import Cache
cache = Cache(str(CACHE_DIR))
data = cache.get(key, default=None, expire=CACHE_TTL["prices"])
```

The `FileCache` class in TASK-003 can still be implemented as a thin wrapper around diskcache to maintain the same interface for tools, but the underlying storage engine should be diskcache, not raw JSON files.

**Alternatives considered:**
| Alternative | Why Rejected |
|------------|-------------|
| Raw JSON files (current plan) | No atomicity, no eviction, no concurrency safety |
| SQLite (direct) | Reinventing diskcache. More code to maintain for the same result. |
| Redis | External process dependency. Overkill for a single-user CLI tool. |
| lru_cache / functools | In-memory only. Does not persist across sessions. |

**Recommended pin:** `diskcache>=5.6,<6.0`

**Risk:** diskcache stores data in SQLite files. If the cache directory is on a network filesystem (NFS), SQLite locking may fail. This is unlikely for a local `~/.zaza/cache/` directory but worth noting.

---

## 5. Computation Layer

### 5.1 DataFrames

#### Recommendation: pandas (confirmed, not polars)

**Current version:** 2.2.x (stable)
**GitHub:** [pandas-dev/pandas](https://github.com/pandas-dev/pandas)

**Why pandas over polars for Zaza:**

1. **Ecosystem compatibility:** yfinance returns pandas DataFrames. The `ta` library operates on pandas DataFrames. statsmodels expects pandas Series/DataFrames. Prophet expects pandas DataFrames with `ds` and `y` columns. Switching to polars would require conversion at every boundary, negating polars' performance advantage.

2. **Dataset size:** Zaza processes at most 1-5 years of daily OHLCV data per tool call (250-1250 rows). At this scale, polars offers no meaningful speedup. Polars shines at >100k rows; Zaza operates at <2k rows per computation.

3. **Developer familiarity:** pandas is the lingua franca of Python financial computation. Every TA library, every stats library, every financial tutorial uses pandas.

**When to reconsider:** If Zaza adds intraday data (1-minute bars, 390 rows/day x 252 days = 98k rows/year) or batch screening across 1000+ tickers simultaneously, polars would provide meaningful speedup for those specific operations.

**Recommended pin:** `pandas>=2.1,<3.0`

**Risk:** pandas 3.0 is in development and will introduce breaking changes (copy-on-write default, nullable dtypes). Pin below 3.0 and monitor.

### 5.2 Technical Analysis

#### Recommendation: `ta` library (confirmed, with awareness of alternatives)

**GitHub:** [bukosabino/ta](https://github.com/bukosabino/ta) (~4.3k stars)
**PyPI:** [ta](https://pypi.org/project/ta/)

**Why:** Pure Python (no C compilation needed), works directly with pandas DataFrames, covers all standard indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ADX, OBV, MFI, ATR, etc.), and is straightforward to install on any platform.

**Alternatives evaluated:**

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| `ta` | Pure Python, easy install, pandas-native | Slower than C-based TA-Lib, less actively maintained | **Use this** |
| `TA-Lib` (C wrapper) | Fastest (C implementation), industry standard | Notoriously difficult to install (requires C library compilation), breaks uv/pip workflows, platform-specific pain | Reject for v0.1 |
| `pandas-ta` | 150+ indicators, pandas extension | Original maintainer abandoned project (GitHub repo deleted), forks exist but fragmented community | Reject due to maintenance uncertainty |
| `pandas-ta-classic` | Fork of pandas-ta | Newer fork, uncertain long-term maintenance | Monitor but do not adopt yet |

**Performance note:** At Zaza's scale (~1000 rows per computation), the performance difference between `ta` (pure Python) and TA-Lib (C) is negligible (milliseconds vs. microseconds). TA-Lib's advantage matters only for backtesting millions of rows or real-time tick processing.

**Recommended pin:** `ta>=0.11,<1.0`

**Risk:** The `ta` library has slower release cadence than ideal. If a bug is found, patches may take time. Mitigate by wrapping indicator calls in `utils/indicators.py` so individual indicators can be replaced with manual pandas computations if needed.

### 5.3 Statistical and Quantitative Libraries

| Library | Use Case | Version | Status | Assessment |
|---------|----------|---------|--------|------------|
| **statsmodels** | ARIMA forecasting | 0.14.6 (Dec 2025) | Active, stable | **Keep.** Gold standard for ARIMA in Python. Use `statsmodels.tsa.arima.model.ARIMA` (new API). |
| **arch** | GARCH(1,1) volatility | 8.0.0 (Oct 2025) | Active, stable | **Keep.** The only mature Python library for ARCH/GARCH family models. Well-maintained by Kevin Sheppard. |
| **prophet** | Time series forecasting | 1.1.6 | Maintained but "finished" | **Keep with caution.** Works well for trend + seasonality decomposition. Heavy dependency (cmdstanpy/pystan). See risks below. |
| **scipy** | Statistical distributions, optimization | 1.14.x | Very active | **Keep.** Foundational scientific computing library. Used for distribution fitting, statistical tests, optimization. |
| **numpy** | Numerical computation, Monte Carlo | 2.1.x | Very active | **Keep.** Foundational. Used for Monte Carlo (random number generation), array operations, linear algebra. |

**Prophet-specific risks:**
- Prophet pulls in `cmdstanpy` which compiles C++ Stan models. This can fail on some platforms or in CI environments.
- Prophet's original creator has described it as "finished" (no new features planned). Bug fixes and maintenance continue but at a slower pace.
- Installation can add 200-500MB of Stan compiler artifacts.

**Prophet mitigation:**
- Make Prophet an optional dependency: `prophet>=1.1; extra == "forecast"`
- In `get_price_forecast`, handle `ImportError` for prophet and fall back to ARIMA-only mode.
- Document the optional nature in setup instructions.

**Recommended pins:**
```
statsmodels>=0.14,<0.16
arch>=7.0,<9.0
prophet>=1.1,<2.0  # optional
scipy>=1.11,<2.0
numpy>=1.26,<3.0
```

**Risk for numpy:** numpy 2.0 introduced breaking C API changes. Most downstream libraries (pandas, scipy, statsmodels) now support numpy 2.x, but verify all dependencies are compatible before allowing numpy>=2.0. The current ecosystem has largely adapted, so `numpy>=1.26,<3.0` is safe.

---

## 6. Web Scraping and HTTP

### Recommendation: httpx (confirmed) + beautifulsoup4 (confirmed)

**httpx:**
- **GitHub:** [encode/httpx](https://github.com/encode/httpx) (~13k stars)
- **Current version:** 0.28.x
- **Why:** Supports both sync and async modes, HTTP/2 support, modern API similar to requests, excellent for an MCP server that may need both sync (simple fetches) and async (concurrent scraping) patterns.

**beautifulsoup4:**
- **Current version:** 4.12.x
- **Why:** The standard HTML parsing library. Combined with `lxml` as the parser backend, it handles the messy HTML from CNN Fear & Greed and FINRA ADF pages reliably.

**Specific guidance:**
- Use `httpx.AsyncClient` for all HTTP calls within async MCP tool handlers.
- Create a shared client instance (connection pooling) rather than creating a new client per request.
- Add `lxml` as a dependency for beautifulsoup4's fastest parser backend.

**Alternatives considered:**
| Alternative | Why Rejected |
|------------|-------------|
| `aiohttp` | Faster for pure high-concurrency async, but async-only (no sync mode). httpx is more versatile and Zaza does not need 1000+ concurrent connections. |
| `requests` | Sync-only. Would block the asyncio event loop. Superseded by httpx for async projects. |
| `selectolax` / `parsel` | Faster HTML parsing but smaller ecosystems. beautifulsoup4 has universal documentation and community support. Not worth the learning curve savings. |

**Recommended pins:**
```
httpx>=0.25,<1.0
beautifulsoup4>=4.12,<5.0
lxml>=5.0,<6.0
```

---

## 7. Browser Automation

### Recommendation: Playwright (confirmed)

**GitHub:** [microsoft/playwright-python](https://github.com/microsoft/playwright-python)
**Current version:** 1.50.x
**PyPI:** [playwright](https://pypi.org/project/playwright/)

**Why:** Playwright is the correct choice for Zaza's browser automation needs. It is faster than Selenium, has built-in auto-waiting (reduces flaky behavior), supports async natively (critical for an MCP server), and is the dominant browser automation tool as of 2025-2026. Microsoft actively maintains it.

**Specific guidance:**
- Use `playwright.async_api` throughout (consistent with the MCP server's async runtime).
- Maintain a persistent browser instance per MCP server session (already planned). Launch on first `navigate` call, reuse for subsequent calls, close on `close` tool call or server shutdown.
- Install only Chromium: `playwright install chromium` (not all browsers).
- Set `headless=True` for the MCP server context.

**Alternatives considered:**
| Alternative | Why Rejected |
|------------|-------------|
| Selenium | Slower, requires separate WebDriver binary management, no built-in auto-wait, larger overhead. Legacy tool. |
| Puppeteer (via pyppeteer) | Node.js native; Python bindings are unofficial and poorly maintained. |
| `requests-html` | Limited JavaScript rendering. Not sufficient for dynamic financial sites. |

**Recommended pin:** `playwright>=1.40,<2.0`

**Risk:** Playwright downloads browser binaries (~200MB for Chromium). This is a one-time setup cost. Document it in setup instructions. In CI, cache the browser binary to avoid re-download on every run.

---

## 8. Docker Integration

### Recommendation: subprocess-based docker exec (confirmed, with asyncio wrapping)

**Why:** The architecture's approach of using `subprocess.run(["docker", "exec", ...])` to communicate with the PKScreener Docker sidecar is pragmatic and correct. PKScreener is a CLI application, not a library. Docker exec is the simplest integration pattern.

**Critical improvement:** Wrap `subprocess.run` with `asyncio.to_thread()` or use `asyncio.create_subprocess_exec()` to avoid blocking the MCP server's event loop during screening operations (which can take 30-120 seconds).

```python
import asyncio

async def run_pkscreener(args: list[str], timeout: int = 120) -> str:
    """Execute a PKScreener command inside the Docker container (non-blocking)."""
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", CONTAINER_NAME,
        "python3", "pkscreener/pkscreenercli.py", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"PKScreener timed out after {timeout}s")
    if proc.returncode != 0:
        raise RuntimeError(f"PKScreener error: {stderr.decode()}")
    return stdout.decode()
```

**Alternatives considered:**
| Alternative | Why Rejected |
|------------|-------------|
| Docker SDK for Python (`docker` package) | Adds a dependency for something `subprocess` handles fine. The Docker SDK is useful for container lifecycle management, but Zaza only needs `exec`. |
| Direct import of PKScreener modules | Fragile, dependency conflicts (TA-Lib C library, TensorFlow), version coupling. The architecture document correctly rejects this. |
| HTTP API on PKScreener container | Would require modifying PKScreener to add a REST API. Upstream maintenance burden. Not worth it. |

**Risk:** `docker exec` requires the Docker daemon to be running and the container to be started. Add a health check at MCP server startup that verifies the container is running and logs a warning (not an error) if it is not, since screening tools are not required for core functionality.

---

## 9. Testing

### Recommendation: pytest + pytest-asyncio (confirmed) + additional tools

**Core testing stack:**

| Tool | Purpose | Pin |
|------|---------|-----|
| `pytest` | Test runner | `>=8.0,<9.0` |
| `pytest-asyncio` | Async test support | `>=0.23,<1.0` |
| `pytest-cov` | Coverage reporting | `>=5.0,<6.0` |
| `respx` | httpx mock library | `>=0.21,<1.0` |
| `pytest-timeout` | Prevent hanging tests | `>=2.2,<3.0` |

**New additions explained:**

**`pytest-cov`** ([pytest-dev/pytest-cov](https://github.com/pytest-dev/pytest-cov)): Coverage measurement is essential for a 66-tool project. Set a coverage floor (e.g., 80%) and enforce it in CI. Reports which tools lack test coverage.

**`respx`** ([lundberg/respx](https://github.com/lundberg/respx)): Purpose-built for mocking httpx requests. Since Zaza uses httpx for SEC EDGAR, StockTwits, FRED, and web scraping, respx provides clean request pattern matching and response injection. Superior to generic `unittest.mock.patch` for HTTP testing.

**`pytest-timeout`**: Prevents tests from hanging indefinitely if a mock is misconfigured and a real HTTP call leaks through. Set `timeout = 30` as a default.

**Testing strategy for yfinance:** yfinance does not use httpx internally (it uses `requests` + `curl_cffi`). For yfinance mocking, use `unittest.mock.patch` to mock the yfinance `Ticker` object methods directly, or use `responses` / `requests-mock` to intercept the underlying requests calls.

**Specific guidance:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
timeout = 30
addopts = "--cov=zaza --cov-report=term-missing --cov-fail-under=80"
```

**Alternatives considered:**
| Alternative | Why Rejected |
|------------|-------------|
| `unittest` | No async support without boilerplate. pytest is the standard. |
| `hypothesis` | Property-based testing is valuable for quant models but adds complexity. Consider for v0.2 for Monte Carlo and distribution tests. |
| `VCR.py` / `pytest-recording` | Records and replays HTTP interactions. Useful but couples tests to specific API response formats. Mock-based testing is more explicit. |

---

## 10. Linting and Type Checking

### Recommendation: ruff + mypy (confirmed)

**Ruff:**
- **GitHub:** [astral-sh/ruff](https://github.com/astral-sh/ruff) (~37k stars)
- **Why:** Replaces flake8, isort, black, pyupgrade, and many other tools in a single Rust-based binary. Runs in milliseconds. Pairs perfectly with uv (both from Astral).

**Mypy:**
- **GitHub:** [python/mypy](https://github.com/python/mypy) (~18k stars)
- **Why:** The most mature Python type checker with the largest ecosystem of type stubs and plugins.

**Specific guidance:**
```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "RUF",  # Ruff-specific rules
]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = false               # Start non-strict, tighten over time
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true  # Require type annotations on all functions
check_untyped_defs = true
ignore_missing_imports = true  # yfinance, ta lack complete stubs
```

**Why not strict mypy:** Many financial libraries (yfinance, ta, praw) lack type stubs. Strict mode would require extensive `# type: ignore` annotations. Start with `disallow_untyped_defs` (enforce annotations on Zaza's own code) and `ignore_missing_imports` (tolerate untyped third-party libraries).

**Alternatives considered:**
| Alternative | Why Rejected |
|------------|-------------|
| Pyright | Faster, but mypy has better third-party stub ecosystem and is more forgiving with scientific Python libraries. |
| Ruff's upcoming type checker (ty, formerly Red Knot) | Still in early development as of Feb 2026. Not production-ready. Monitor for future adoption. |
| black (formatter) | Ruff's formatter is a drop-in replacement and faster. No need for a separate tool. |

**Recommended pins:**
```
ruff>=0.8,<1.0
mypy>=1.7,<2.0
```

---

## 11. Serialization

### Recommendation: stdlib `json` for cache/MCP protocol + `orjson` for hot paths

**orjson:**
- **GitHub:** [ijl/orjson](https://github.com/ijl/orjson) (~6.5k stars)
- **PyPI:** [orjson](https://pypi.org/project/orjson/)

**Why a dual approach:**
- The MCP protocol uses stdlib JSON internally (the `mcp` SDK handles serialization). Do not override this.
- For Zaza's own cache writes, tool response construction, and DataFrame-to-JSON conversion, `orjson` provides 3-9x faster serialization than stdlib `json`. This matters when serializing large options chains or multi-year price histories.
- orjson natively handles `datetime`, `numpy.int64`, `numpy.float64`, and `UUID` types without custom serializers, which is a significant convenience when working with pandas/numpy data.

**Usage pattern:**
```python
import orjson

# Serializing tool results
def to_json(data: dict) -> str:
    return orjson.dumps(data, option=orjson.OPT_SERIALIZE_NUMPY).decode()

# Cache writes
cache_bytes = orjson.dumps({"cached_at": time.time(), "data": result})
```

**Alternatives considered:**
| Alternative | Why Rejected |
|------------|-------------|
| `msgspec` | Fastest overall with struct schemas, but adds a new serialization paradigm. orjson is a drop-in replacement for `json.dumps/loads` with no API change. Lower adoption cost. |
| stdlib `json` only | Adequate but measurably slower for large payloads. orjson is a simple addition with immediate benefit. |
| `ujson` | Slower than orjson, less actively maintained, no numpy support. |

**Recommended pin:** `orjson>=3.9,<4.0`

---

## 12. Logging and Observability

### Recommendation: structlog

**GitHub:** [hynek/structlog](https://github.com/hynek/structlog) (~3.5k stars)
**PyPI:** [structlog](https://pypi.org/project/structlog/)

**Why:** The architecture document does not specify a logging approach, which is a gap. An MCP server communicating over stdin/stdout CANNOT use print() or stdlib logging to stdout (it would corrupt the MCP protocol). Structlog provides structured, JSON-formatted logging to stderr or file, with context variables that propagate through async calls.

**Critical constraint:** The MCP server's stdout is reserved for MCP protocol messages. ALL logging MUST go to stderr or a log file.

**Specific guidance:**
```python
import structlog
import logging
import sys

# Configure structlog to write to stderr ONLY
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),  # Human-readable for dev
        # Use structlog.processors.JSONRenderer() for production
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

log = structlog.get_logger()

# In tool handlers:
async def get_price_snapshot(ticker: str) -> dict:
    log.info("fetching_price", ticker=ticker)
    ...
    log.info("price_fetched", ticker=ticker, source="cache" if cached else "api")
```

**What to log:**
- Tool invocations (tool name, parameters, latency)
- Cache hits/misses
- API call latency and response status
- Errors with full context (tool name, parameters, error type)
- PKScreener Docker exec results

**Alternatives considered:**
| Alternative | Why Rejected |
|------------|-------------|
| stdlib `logging` | Unstructured by default. Requires significant configuration to achieve what structlog provides out of the box. |
| `loguru` | Popular and developer-friendly, but defaults to stdout (dangerous for MCP). structlog has better async/contextvars support. |
| No logging | Unacceptable. Debugging a 66-tool MCP server without observability is painful. |

**Recommended pin:** `structlog>=24.0,<26.0`

---

## 13. Error Handling and Resilience

### Recommendation: tenacity (retries) + manual rate limiting + graceful degradation

**tenacity:**
- **GitHub:** [jd/tenacity](https://github.com/jd/tenacity) (~6.5k stars)
- **PyPI:** [tenacity](https://pypi.org/project/tenacity/) (v9.1.4, Feb 2026)

**Why tenacity:** External API calls (yfinance, SEC EDGAR, Reddit, web scraping) fail intermittently due to rate limits, network issues, and upstream changes. tenacity provides configurable retry with exponential backoff, jitter, and exception filtering. It is the standard Python retry library.

**Specific patterns for Zaza:**

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx

# For httpx calls (EDGAR, scraping)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
)
async def fetch_edgar(url: str) -> dict:
    ...

# For yfinance calls
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=2, max=15),
)
def fetch_yfinance_data(ticker: str) -> dict:
    ...
```

**Rate limiting strategy:**
- SEC EDGAR: 10 req/sec (their published limit). Use `asyncio.Semaphore(10)`.
- yfinance: No published limit, but 2-second delay between rapid sequential calls to the same endpoint.
- Reddit API: 60 req/min (PRAW handles this internally).
- Web scraping targets (CNN, FINRA): 1 req/sec per domain.

**Implementation approach:**
```python
import asyncio
from collections import defaultdict
import time

class RateLimiter:
    """Simple token-bucket rate limiter per domain."""
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_call: dict[str, float] = defaultdict(float)

    async def acquire(self, domain: str, min_interval: float = 1.0):
        async with self._locks[domain]:
            elapsed = time.monotonic() - self._last_call[domain]
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_call[domain] = time.monotonic()
```

**Circuit breaker:** Not recommended for v0.1. Zaza is a single-user CLI tool, not a microservice handling thousands of concurrent requests. Simple retry + timeout is sufficient. If a data source is completely down, the retry will exhaust attempts and the tool returns an error message. The user can try again later.

**Graceful degradation principle:** Every tool MUST return a structured error rather than raising an exception that crashes the MCP server. The pattern:

```python
async def get_price_snapshot(ticker: str) -> dict:
    try:
        data = await fetch_price(ticker)
        return {"status": "ok", "data": data}
    except Exception as e:
        log.error("price_fetch_failed", ticker=ticker, error=str(e))
        return {"status": "error", "error": str(e), "suggestion": "Try again or use WebSearch"}
```

**Recommended pin:** `tenacity>=9.0,<10.0`

---

## 14. Gaps Identified in Current Architecture

### 14.1 Missing: Input Validation with Pydantic

**Recommendation: Add `pydantic>=2.5,<3.0`**

The MCP SDK's `FastMCP` module uses Pydantic for tool parameter validation automatically when type hints are provided. However, Zaza should also use Pydantic models for:
- Validating tool return schemas (consistent response structure)
- Defining configuration models (environment variables)
- Documenting tool interfaces via schema generation

The MCP SDK already depends on Pydantic, so this adds no new transitive dependency.

### 14.2 Missing: Logging (addressed in Section 12)

No logging strategy was defined in the architecture. This is critical for an MCP server where stdout is reserved for protocol messages.

### 14.3 Missing: Retry and Resilience (addressed in Section 13)

No retry or rate limiting strategy was defined. Given the reliance on 8 external data sources (several of which are web scrapes), this is essential.

### 14.4 Missing: Health Check / Diagnostics Tool

Consider adding a 67th MCP tool: `get_server_health` that returns:
- Server uptime
- Cache statistics (size, hit rate)
- Data source connectivity status (quick ping to each API)
- PKScreener container status
- Python/dependency versions

This aids debugging when tools fail silently.

### 14.5 Missing: Graceful Shutdown

When Claude Code terminates, the MCP server process should cleanly:
- Close the Playwright browser instance
- Flush any pending cache writes
- Log session statistics

Use Python's `atexit` module or signal handlers for `SIGTERM`/`SIGINT`.

### 14.6 Missing: Data Serialization for pandas/numpy Types

yfinance returns pandas Timestamps, numpy int64/float64, and other types that stdlib `json` cannot serialize. The architecture mentions `default=str` in `json.dumps`, but this is lossy (timestamps become unparseable strings). Using `orjson` (Section 11) handles these types natively and correctly.

---

## Complete Dependency Summary

### Production Dependencies

| Package | Version Pin | Purpose | License |
|---------|------------|---------|---------|
| `mcp` | `>=1.20,<2.0` | MCP server framework | MIT |
| `yfinance` | `>=1.0,<2.0` | Market data, fundamentals, options | Apache 2.0 |
| `pandas` | `>=2.1,<3.0` | DataFrame operations | BSD 3-Clause |
| `ta` | `>=0.11,<1.0` | Technical analysis indicators | MIT |
| `statsmodels` | `>=0.14,<0.16` | ARIMA forecasting | BSD 3-Clause |
| `arch` | `>=7.0,<9.0` | GARCH volatility modeling | NCSA |
| `scipy` | `>=1.11,<2.0` | Statistical distributions, tests | BSD 3-Clause |
| `numpy` | `>=1.26,<3.0` | Numerical computation | BSD 3-Clause |
| `praw` | `>=7.7,<8.0` | Reddit API client | BSD 2-Clause |
| `playwright` | `>=1.40,<2.0` | Browser automation | Apache 2.0 |
| `httpx` | `>=0.25,<1.0` | Async HTTP client | BSD 3-Clause |
| `beautifulsoup4` | `>=4.12,<5.0` | HTML parsing | MIT |
| `lxml` | `>=5.0,<6.0` | Fast HTML parser backend | BSD 3-Clause |
| `diskcache` | `>=5.6,<6.0` | SQLite-backed cache with TTL | Apache 2.0 |
| `orjson` | `>=3.9,<4.0` | Fast JSON serialization | Apache 2.0 / MIT |
| `structlog` | `>=24.0,<26.0` | Structured logging | Apache 2.0 / MIT |
| `tenacity` | `>=9.0,<10.0` | Retry with backoff | Apache 2.0 |

### Optional Production Dependencies

| Package | Version Pin | Purpose | Condition |
|---------|------------|---------|-----------|
| `prophet` | `>=1.1,<2.0` | Prophet forecasting | `extra = "forecast"` |

### Development Dependencies

| Package | Version Pin | Purpose |
|---------|------------|---------|
| `pytest` | `>=8.0,<9.0` | Test runner |
| `pytest-asyncio` | `>=0.23,<1.0` | Async test support |
| `pytest-cov` | `>=5.0,<6.0` | Coverage reporting |
| `pytest-timeout` | `>=2.2,<3.0` | Test timeout enforcement |
| `respx` | `>=0.21,<1.0` | httpx request mocking |
| `ruff` | `>=0.8,<1.0` | Linting + formatting |
| `mypy` | `>=1.7,<2.0` | Type checking |

---

## Recommended pyproject.toml (Updated)

```toml
[project]
name = "zaza"
version = "0.1.0"
description = "Financial research MCP server for Claude Code"
requires-python = ">=3.12"
dependencies = [
    "mcp>=1.20,<2.0",
    "yfinance>=1.0,<2.0",
    "pandas>=2.1,<3.0",
    "ta>=0.11,<1.0",
    "statsmodels>=0.14,<0.16",
    "arch>=7.0,<9.0",
    "scipy>=1.11,<2.0",
    "numpy>=1.26,<3.0",
    "praw>=7.7,<8.0",
    "playwright>=1.40,<2.0",
    "httpx>=0.25,<1.0",
    "beautifulsoup4>=4.12,<5.0",
    "lxml>=5.0,<6.0",
    "diskcache>=5.6,<6.0",
    "orjson>=3.9,<4.0",
    "structlog>=24.0,<26.0",
    "tenacity>=9.0,<10.0",
]

[project.optional-dependencies]
forecast = ["prophet>=1.1,<2.0"]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-asyncio>=0.23,<1.0",
    "pytest-cov>=5.0,<6.0",
    "pytest-timeout>=2.2,<3.0",
    "respx>=0.21,<1.0",
    "ruff>=0.8,<1.0",
    "mypy>=1.7,<2.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/zaza"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = false
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
check_untyped_defs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
timeout = 30
addopts = "--cov=zaza --cov-report=term-missing --cov-fail-under=80"
```

---

## Decision Summary Table

| Category | Current Plan | Recommendation | Change? |
|----------|-------------|----------------|---------|
| Python | >=3.12 | >=3.12 (confirmed) | No |
| MCP SDK | `mcp` (low-level Server) | `mcp` with `FastMCP` sub-module | Minor |
| Package manager | uv | uv (confirmed) | No |
| Market data | yfinance | yfinance (confirmed, with abstraction layer) | No |
| HTTP client | httpx | httpx (confirmed) | No |
| HTML parser | beautifulsoup4 | beautifulsoup4 + lxml backend | Minor |
| Cache | Custom FileCache (JSON files) | **diskcache** (SQLite-backed) | **Yes** |
| DataFrames | pandas | pandas (confirmed, not polars) | No |
| TA indicators | ta | ta (confirmed) | No |
| Stats | statsmodels | statsmodels (confirmed) | No |
| GARCH | arch | arch (confirmed) | No |
| Forecasting | prophet | prophet (confirmed, made optional) | Minor |
| Browser | Playwright | Playwright (confirmed) | No |
| Docker exec | subprocess.run | **asyncio.create_subprocess_exec** | **Yes** |
| JSON serialization | stdlib json | **orjson** (for Zaza's own serialization) | **Yes** |
| Logging | Not specified | **structlog** (to stderr) | **New** |
| Retries | Not specified | **tenacity** | **New** |
| Rate limiting | Not specified | **Manual asyncio.Semaphore** | **New** |
| Input validation | Not specified | **Pydantic** (via MCP SDK) | **New** |
| Test coverage | Not specified | **pytest-cov** | **New** |
| HTTP mocking | Not specified | **respx** | **New** |
| Test timeout | Not specified | **pytest-timeout** | **New** |

**Total new dependencies added:** 6 (diskcache, orjson, structlog, tenacity, lxml, respx)
**Total dependencies removed:** 0
**Net impact:** Modest increase in dependency count, each filling a clear gap with a well-maintained, focused library.

---

## References

- [MCP Python SDK - GitHub](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Python SDK - PyPI](https://pypi.org/project/mcp/)
- [FastMCP - GitHub](https://github.com/jlowin/fastmcp)
- [yfinance - GitHub](https://github.com/ranaroussi/yfinance)
- [uv - GitHub](https://github.com/astral-sh/uv)
- [uv Documentation](https://docs.astral.sh/uv/)
- [pandas - GitHub](https://github.com/pandas-dev/pandas)
- [Polars - Benchmarks](https://pola.rs/posts/benchmarks/)
- [ta library - GitHub](https://github.com/bukosabino/ta)
- [pandas-ta - PyPI](https://pypi.org/project/pandas-ta/)
- [TA-Lib vs pandas-ta comparison](https://www.slingacademy.com/article/comparing-ta-lib-to-pandas-ta-which-one-to-choose/)
- [statsmodels - PyPI](https://pypi.org/project/statsmodels/)
- [arch library - GitHub](https://github.com/bashtage/arch)
- [Prophet - GitHub](https://github.com/facebook/prophet)
- [httpx - GitHub](https://github.com/encode/httpx)
- [httpx vs requests vs aiohttp](https://oxylabs.io/blog/httpx-vs-requests-vs-aiohttp)
- [Playwright - GitHub](https://github.com/microsoft/playwright-python)
- [Playwright vs Selenium 2025](https://www.browserless.io/blog/playwright-vs-selenium-2025-browser-automation-comparison)
- [diskcache - GitHub](https://github.com/grantjenks/python-diskcache)
- [diskcache deep dive](https://www.bitecode.dev/p/diskcache-more-than-caching)
- [orjson - GitHub](https://github.com/ijl/orjson)
- [msgspec benchmarks](https://jcristharif.com/msgspec/benchmarks.html)
- [structlog - PyPI](https://pypi.org/project/structlog/)
- [structlog async logging 2026](https://johal.in/structlog-contextvars-python-async-logging-2026/)
- [tenacity - GitHub](https://github.com/jd/tenacity)
- [tenacity - PyPI](https://pypi.org/project/tenacity/)
- [Ruff - GitHub](https://github.com/astral-sh/ruff)
- [Modern Python toolkit: Ruff + mypy](https://simone-carolini.medium.com/modern-python-code-quality-setup-uv-ruff-and-mypy-8038c6549dcc)
- [respx - GitHub](https://github.com/lundberg/respx)
- [pytest-cov - GitHub](https://github.com/pytest-dev/pytest-cov)
- [yfinance alternatives 2025](https://medium.com/@craakash/9-best-yfinance-alternatives-for-reliable-financial-data-in-2025-b48b4aaa9ac9)
