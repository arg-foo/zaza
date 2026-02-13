# TASK-015: Technical Analysis Tools

## Task ID
TASK-015

## Status
PENDING

## Title
Implement Technical Analysis Tools (9 Tools)

## Description
Implement all 9 technical analysis MCP tools. Each tool takes a ticker and optional period, internally fetches OHLCV data via the yfinance client, computes indicators using the shared TA utilities, and returns structured JSON with numeric values and pre-computed signal summaries.

These 9 tools cover orthogonal TA dimensions: trend, momentum, volatility, volume, levels, patterns, money flow, trend strength, and relative performance.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/ta/moving_averages.py` — `get_moving_averages(ticker, period="6mo")`: SMA(20,50,200), EMA(12,26), price vs. each MA, golden/death cross status
- [ ] `src/zaza/tools/ta/momentum.py` — `get_momentum_indicators(ticker, period="6mo")`: RSI(14), MACD(12/26/9), Stochastic %K/%D with signal summaries
- [ ] `src/zaza/tools/ta/volatility.py` — `get_volatility_indicators(ticker, period="6mo")`: Bollinger Bands(20,2σ), ATR(14), price position within bands
- [ ] `src/zaza/tools/ta/volume.py` — `get_volume_analysis(ticker, period="6mo")`: OBV, VWAP, volume trend vs. 20-day average
- [ ] `src/zaza/tools/ta/support_resistance.py` — `get_support_resistance(ticker, period="1y")`: pivot points, Fibonacci retracements (23.6/38.2/50/61.8%), 52-week high/low
- [ ] `src/zaza/tools/ta/trend_strength.py` — `get_trend_strength(ticker, period="6mo")`: ADX(14), +DI/-DI, Ichimoku Cloud components, cloud color, price position relative to cloud
- [ ] `src/zaza/tools/ta/patterns.py` — `get_price_patterns(ticker, period="3mo")`: candlestick patterns (doji, hammer, engulfing, stars), chart patterns, confidence scores
- [ ] `src/zaza/tools/ta/money_flow.py` — `get_money_flow(ticker, period="6mo")`: CMF(20), MFI(14), Williams %R(14), A/D line, divergence signals
- [ ] `src/zaza/tools/ta/relative.py` — `get_relative_performance(ticker, period="6mo")`: performance vs. S&P 500 + sector ETF, beta, correlation, sector percentile rank
- [ ] All tools registered as MCP tools via `register_ta_tools(app)`
- [ ] Each tool internally fetches OHLCV via YFinanceClient + cache
- [ ] Each returns both raw values AND pre-computed signal summaries

### Non-Functional Requirements
- [ ] **Testing**: Unit tests per tool with known OHLCV data; verify indicator values and signal classifications
- [ ] **Performance**: Each tool should complete in <2 seconds (including cache check)
- [ ] **Reliability**: Handle insufficient data (e.g., IPO < 200 days ago for SMA-200) by returning null for those indicators
- [ ] **Documentation**: Each MCP tool has a clear description and parameter schema

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance API client
- TASK-006: MCP server entry point
- TASK-009: Shared TA utilities

## Technical Notes

### Common Tool Pattern
Every TA tool follows this flow:
```python
@app.tool()
async def get_momentum_indicators(ticker: str, period: str = "6mo") -> str:
    """Get RSI, MACD, and Stochastic oscillators with signal summaries."""
    # 1. Fetch OHLCV
    history = yf_client.get_history(ticker, period=period)
    df = ohlcv_to_dataframe(history)

    # 2. Compute indicators
    rsi = compute_rsi(df)
    macd = compute_macd(df)
    stochastic = compute_stochastic(df)

    # 3. Return structured JSON
    result = {
        "ticker": ticker, "period": period,
        "indicators": {**rsi, **macd, **stochastic},
        "signals": {
            "rsi": rsi["signal"],
            "macd": macd["signal"],
            "stochastic": stochastic["signal"],
        }
    }
    return json.dumps(result)
```

### Relative Performance
`get_relative_performance` needs to fetch both the ticker's history AND the S&P 500 (^GSPC) + sector ETF. Use sector mapping:
```python
SECTOR_ETFS = {
    "Technology": "XLK", "Healthcare": "XLV", "Financial Services": "XLF",
    "Consumer Cyclical": "XLY", "Communication Services": "XLC",
    "Industrials": "XLI", "Consumer Defensive": "XLP", "Energy": "XLE",
    "Utilities": "XLU", "Real Estate": "XLRE", "Basic Materials": "XLB",
}
```

### Candlestick Pattern Detection
Use `ta` library's `talib` integration or implement common patterns:
- Doji: open ≈ close (body < 10% of range)
- Hammer: small body at top, long lower shadow (>2x body)
- Engulfing: current candle body encompasses prior candle body
- Morning/Evening star: three-candle reversal pattern

### Implementation Hints
1. Period parameter maps to yfinance's period strings: "1mo", "3mo", "6mo", "1y", "2y", "5y"
2. Some tools need more history than the period (e.g., 200-day SMA needs at least 200 data points)
3. The `get_relative_performance` tool needs the company's sector (from `get_company_facts` or yfinance .info)
4. Each tool file should export a `register(app)` function that the top-level `register_ta_tools` calls

## Estimated Complexity
**Large** (10-14 hours)

## References
- ZAZA_ARCHITECTURE.md Section 8 (Technical Analysis Sub-Tools)
- ZAZA_ARCHITECTURE.md Section 8.1 (Tool Specifications)
