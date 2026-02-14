# TASK-016: Options & Derivatives Tools

## Task ID
TASK-016

## Status
COMPLETED

## Title
Implement Options & Derivatives Tools (7 Tools)

## Description
Implement 7 options and derivatives MCP tools for directional bias, positioning analysis, and implied expectations. Source data comes from yfinance's options chain; derived metrics (IV rank, Greeks, GEX, max pain) are computed locally.

These tools power the Options Analysis sub-agent and can be called inline for simple IV/P/C queries.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/tools/options/chain.py`:
  - `get_options_expirations(ticker)` — list of available expiration dates
  - `get_options_chain(ticker, expiration_date)` — calls + puts with strike, last, bid, ask, volume, OI, IV per contract
- [ ] `src/zaza/tools/options/volatility.py`:
  - `get_implied_volatility(ticker)` — ATM IV, 30-day IV rank, IV percentile over 1Y, historical IV (30/60/90d), IV skew (25-delta put IV vs 25-delta call IV)
- [ ] `src/zaza/tools/options/flow.py`:
  - `get_options_flow(ticker)` — unusual activity (volume >> OI), large notional trades, net directional bias, sweep detection
  - `get_put_call_ratio(ticker)` — P/C by volume, P/C by OI, vs. 20-day average, equity vs. index context
- [ ] `src/zaza/tools/options/levels.py`:
  - `get_max_pain(ticker, expiration_date)` — max pain price, distance from current price, OI distribution by strike
  - `get_gamma_exposure(ticker)` — net GEX by strike, GEX flip point, positive/negative gamma zones, dealer hedging levels
- [ ] All 7 tools registered as MCP tools via `register_options_tools(app)`
- [ ] Options chain cached with 30-minute TTL
- [ ] Default to nearest monthly expiry when no date specified

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with synthetic options chain data; verify GEX, max pain, and IV calculations
- [ ] **Performance**: Options tools should complete in <3 seconds
- [ ] **Reliability**: Handle tickers with no options data gracefully
- [ ] **Documentation**: MCP tool descriptions explain what each metric means

## Dependencies
- TASK-001: Project scaffolding
- TASK-003: File-based cache
- TASK-004: yfinance API client
- TASK-006: MCP server entry point

## Technical Notes

### IV Rank & Percentile
```python
# IV Rank = (current_IV - 1Y_low_IV) / (1Y_high_IV - 1Y_low_IV)
# IV Percentile = % of days in past year where IV was below current IV
# IV Skew = 25-delta put IV - 25-delta call IV
```

### Max Pain Calculation
```python
def calculate_max_pain(chain):
    """Find strike where total option holder losses are maximized."""
    strikes = sorted(set(chain.calls.strike) | set(chain.puts.strike))
    min_pain, max_pain_strike = float("inf"), 0
    for strike in strikes:
        call_pain = sum(max(0, strike - s) * oi for s, oi in zip(chain.calls.strike, chain.calls.openInterest))
        put_pain = sum(max(0, s - strike) * oi for s, oi in zip(chain.puts.strike, chain.puts.openInterest))
        total = call_pain + put_pain
        if total < min_pain:
            min_pain, max_pain_strike = total, strike
    return max_pain_strike
```

### Gamma Exposure (GEX)
```python
# For each strike:
#   Call GEX = call_OI * call_gamma * 100 * spot_price
#   Put GEX = -put_OI * put_gamma * 100 * spot_price  (negative because puts)
#   Net GEX = Call GEX + Put GEX
# GEX flip point = strike where net GEX transitions from positive to negative
# Positive GEX zone: dealers long gamma → dampens price moves (pinning)
# Negative GEX zone: dealers short gamma → amplifies moves (volatility)
```

### Implementation Hints
1. yfinance options data is delayed 15-20 min — sufficient for positioning, not real-time trading
2. Greeks from yfinance are approximate (Black-Scholes) — sufficient for GEX direction
3. For IV rank, need 1 year of historical ATM IV — compute from historical options chains or approximate from historical volatility
4. Unusual flow detection: flag contracts where `volume > 3 * openInterest`
5. Put/Call ratio context: equity P/C > 1.0 is bearish, < 0.7 is bullish (rough guides)

## Estimated Complexity
**Large** (10-14 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.5 (Options & Derivatives Tools)
- ZAZA_ARCHITECTURE.md Section 6.2.6 (Options Analysis Agent)
