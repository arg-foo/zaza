"""Tests for options & derivatives tools (TASK-016)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Synthetic options data helpers
# ---------------------------------------------------------------------------

def _make_chain(
    current_price: float = 100.0,
    strikes: list[float] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build a synthetic options chain around *current_price*."""
    strikes = strikes or [90, 95, 100, 105, 110]
    calls = []
    puts = []
    for s in strikes:
        calls.append({
            "strike": s,
            "lastPrice": max(0, current_price - s) + 2.0,
            "bid": max(0, current_price - s) + 1.5,
            "ask": max(0, current_price - s) + 2.5,
            "volume": 500 if s == 100 else 100,
            "openInterest": 1000 if s == 100 else 200,
            "impliedVolatility": 0.30 + (s - current_price) * 0.002,
            "inTheMoney": s < current_price,
            "contractSymbol": f"AAPL250321C{int(s * 1000):08d}",
        })
        puts.append({
            "strike": s,
            "lastPrice": max(0, s - current_price) + 2.0,
            "bid": max(0, s - current_price) + 1.5,
            "ask": max(0, s - current_price) + 2.5,
            "volume": 300 if s == 100 else 80,
            "openInterest": 800 if s == 100 else 150,
            "impliedVolatility": 0.30 - (s - current_price) * 0.002,
            "inTheMoney": s > current_price,
            "contractSymbol": f"AAPL250321P{int(s * 1000):08d}",
        })
    return {"calls": calls, "puts": puts}


EXPIRATIONS = ["2025-03-21", "2025-04-18", "2025-05-16", "2025-06-20"]


def _make_quote(price: float = 100.0) -> dict[str, Any]:
    return {
        "regularMarketPrice": price,
        "symbol": "AAPL",
    }


def _make_history(n: int = 252) -> list[dict[str, Any]]:
    """Fake 1-year daily history with constant close."""
    return [{"Close": 100.0 + (i % 5) * 0.5} for i in range(n)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.get.return_value = None  # always miss
    cache.make_key.side_effect = lambda *a, **kw: f"key_{'_'.join(str(v) for v in a)}"
    return cache


@pytest.fixture()
def mock_yf(mock_cache: MagicMock) -> MagicMock:
    yf = MagicMock()
    yf.cache = mock_cache
    yf.get_options_expirations.return_value = EXPIRATIONS
    yf.get_options_chain.return_value = _make_chain()
    yf.get_quote.return_value = _make_quote()
    yf.get_history.return_value = _make_history()
    return yf


# ===========================================================================
# chain.py tests
# ===========================================================================

class TestGetOptionsExpirations:
    """get_options_expirations tool tests."""

    async def test_returns_expiration_dates(
        self, mock_yf: MagicMock, mock_cache: MagicMock
    ) -> None:
        from zaza.tools.options.chain import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_options_expirations"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert result["expirations"] == EXPIRATIONS
        assert result["count"] == 4

    async def test_empty_expirations(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_expirations.return_value = []
        from zaza.tools.options.chain import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_options_expirations"]("XYZ"))
        assert result["expirations"] == []
        assert result["count"] == 0


class TestGetOptionsChain:
    """get_options_chain tool tests."""

    async def test_returns_chain_data(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        from zaza.tools.options.chain import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_options_chain"]("AAPL", "2025-03-21"))
        assert result["ticker"] == "AAPL"
        assert "calls" in result
        assert "puts" in result
        assert len(result["calls"]) == 5
        assert len(result["puts"]) == 5
        # Each call should have the expected fields
        call = result["calls"][0]
        expected_fields = [
            "strike", "lastPrice", "bid", "ask",
            "volume", "openInterest", "impliedVolatility",
        ]
        for field in expected_fields:
            assert field in call

    async def test_empty_chain(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_chain.return_value = {"calls": [], "puts": []}
        from zaza.tools.options.chain import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_options_chain"]("XYZ", "2025-03-21"))
        assert result["calls"] == []
        assert result["puts"] == []


# ===========================================================================
# volatility.py tests
# ===========================================================================

class TestGetImpliedVolatility:
    """get_implied_volatility tool tests."""

    async def test_returns_iv_data(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        from zaza.tools.options.volatility import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_implied_volatility"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert "atm_iv" in result
        assert "iv_rank" in result
        assert "iv_skew" in result
        assert isinstance(result["atm_iv"], float)
        assert isinstance(result["iv_rank"], float)

    async def test_iv_no_chain_data(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_expirations.return_value = []
        from zaza.tools.options.volatility import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_implied_volatility"]("XYZ"))
        assert "error" in result

    async def test_iv_skew_positive_when_puts_more_expensive(
        self, mock_yf: MagicMock, mock_cache: MagicMock
    ) -> None:
        """When OTM puts have higher IV than OTM calls, skew should be positive."""
        # Build chain where OTM put IV is clearly higher than OTM call IV
        chain: dict[str, list[dict[str, Any]]] = {"calls": [], "puts": []}
        for s in [90, 95, 100, 105, 110]:
            chain["calls"].append({
                "strike": s,
                "lastPrice": 2.0,
                "bid": 1.5,
                "ask": 2.5,
                "volume": 100,
                "openInterest": 200,
                # OTM calls (strike > 100) have LOW IV
                "impliedVolatility": 0.25 if s > 100 else 0.30,
                "inTheMoney": s < 100,
            })
            chain["puts"].append({
                "strike": s,
                "lastPrice": 2.0,
                "bid": 1.5,
                "ask": 2.5,
                "volume": 100,
                "openInterest": 200,
                # OTM puts (strike < 100) have HIGH IV
                "impliedVolatility": 0.40 if s < 100 else 0.30,
                "inTheMoney": s > 100,
            })
        mock_yf.get_options_chain.return_value = chain

        from zaza.tools.options.volatility import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_implied_volatility"]("AAPL"))
        # Skew = OTM put IV (avg 0.40) - OTM call IV (avg 0.25) > 0
        assert result["iv_skew"] > 0


# ===========================================================================
# flow.py tests
# ===========================================================================

class TestGetOptionsFlow:
    """get_options_flow tool tests."""

    async def test_detects_unusual_volume(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        # ATM strike has volume=500, OI=1000 for calls => vol/OI = 0.5
        # Other strikes have volume=100, OI=200 => vol/OI = 0.5
        # To get unusual activity, set one strike with vol >> OI
        chain = _make_chain()
        chain["calls"][2]["volume"] = 5000  # ATM call huge volume
        chain["calls"][2]["openInterest"] = 100
        mock_yf.get_options_chain.return_value = chain

        from zaza.tools.options.flow import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_options_flow"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert len(result["unusual_activity"]) > 0
        # The ATM call with huge volume should be flagged
        unusual = result["unusual_activity"][0]
        assert unusual["strike"] == 100
        assert unusual["type"] == "call"

    async def test_flow_with_no_data(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_expirations.return_value = []
        from zaza.tools.options.flow import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_options_flow"]("XYZ"))
        assert result["unusual_activity"] == []


class TestGetPutCallRatio:
    """get_put_call_ratio tool tests."""

    async def test_returns_ratios(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        from zaza.tools.options.flow import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_put_call_ratio"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert "pc_volume_ratio" in result
        assert "pc_oi_ratio" in result
        assert "interpretation" in result
        # Put volume < call volume in our synthetic data
        assert isinstance(result["pc_volume_ratio"], float)

    async def test_put_call_ratio_no_data(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_expirations.return_value = []
        from zaza.tools.options.flow import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_put_call_ratio"]("XYZ"))
        assert "error" in result


# ===========================================================================
# levels.py tests
# ===========================================================================

class TestGetMaxPain:
    """get_max_pain tool tests."""

    async def test_max_pain_calculation(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        from zaza.tools.options.levels import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_max_pain"]("AAPL", "2025-03-21"))
        assert result["ticker"] == "AAPL"
        assert "max_pain_strike" in result
        assert "current_price" in result
        assert "distance_pct" in result
        # Max pain should be one of the strikes
        assert result["max_pain_strike"] in [90, 95, 100, 105, 110]

    async def test_max_pain_with_known_data(
        self, mock_yf: MagicMock, mock_cache: MagicMock
    ) -> None:
        """Test max pain with specifically crafted data where we know the answer."""
        # Create chain with massive OI at strike 100
        chain: dict[str, list[dict[str, Any]]] = {"calls": [], "puts": []}
        for s in [95, 100, 105]:
            chain["calls"].append({
                "strike": s,
                "openInterest": 10000 if s == 100 else 10,
                "volume": 100,
                "lastPrice": 2.0,
                "bid": 1.5,
                "ask": 2.5,
                "impliedVolatility": 0.3,
            })
            chain["puts"].append({
                "strike": s,
                "openInterest": 10000 if s == 100 else 10,
                "volume": 100,
                "lastPrice": 2.0,
                "bid": 1.5,
                "ask": 2.5,
                "impliedVolatility": 0.3,
            })
        mock_yf.get_options_chain.return_value = chain

        from zaza.tools.options.levels import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_max_pain"]("AAPL", "2025-03-21"))
        # With massive OI at 100 for both calls and puts, max pain should be 100
        assert result["max_pain_strike"] == 100

    async def test_max_pain_defaults_to_nearest_expiry(
        self, mock_yf: MagicMock, mock_cache: MagicMock
    ) -> None:
        """If no expiration_date given, use nearest monthly expiry."""
        from zaza.tools.options.levels import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_max_pain"]("AAPL"))
        assert "max_pain_strike" in result
        # Should have used the first expiration date
        assert result["expiration_date"] == EXPIRATIONS[0]

    async def test_max_pain_no_expirations(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_expirations.return_value = []
        from zaza.tools.options.levels import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_max_pain"]("XYZ"))
        assert "error" in result


class TestGetGammaExposure:
    """get_gamma_exposure tool tests."""

    async def test_gex_returns_data(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        from zaza.tools.options.levels import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_gamma_exposure"]("AAPL"))
        assert result["ticker"] == "AAPL"
        assert "gex_by_strike" in result
        assert "net_gex" in result
        assert "gex_flip_point" in result
        assert isinstance(result["gex_by_strike"], list)

    async def test_gex_no_data(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_expirations.return_value = []
        from zaza.tools.options.levels import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_gamma_exposure"]("XYZ"))
        assert "error" in result

    async def test_gex_flip_point(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        """GEX flip point should be a strike value or null."""
        from zaza.tools.options.levels import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_gamma_exposure"]("AAPL"))
        flip = result["gex_flip_point"]
        # flip point should be a number or None
        assert flip is None or isinstance(flip, (int, float))


# ===========================================================================
# __init__.py register_options_tools tests
# ===========================================================================

class TestRegisterOptionsTools:
    """Test that register_options_tools registers all 7 tools."""

    async def test_registers_all_tools(self) -> None:
        from zaza.tools.options import register_options_tools
        mcp = MagicMock()
        registered: list[str] = []
        mcp.tool.return_value = lambda fn: registered.append(fn.__name__) or fn
        register_options_tools(mcp)
        expected = {
            "get_options_expirations",
            "get_options_chain",
            "get_implied_volatility",
            "get_options_flow",
            "get_put_call_ratio",
            "get_max_pain",
            "get_gamma_exposure",
        }
        assert set(registered) == expected


# ===========================================================================
# Error handling tests
# ===========================================================================

class TestOptionsErrorHandling:
    """Ensure tools return JSON error dicts on exceptions, never raise."""

    async def test_chain_exception(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_chain.side_effect = Exception("network error")
        from zaza.tools.options.chain import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_options_chain"]("AAPL", "2025-03-21"))
        assert "error" in result

    async def test_flow_exception(self, mock_yf: MagicMock, mock_cache: MagicMock) -> None:
        mock_yf.get_options_chain.side_effect = Exception("timeout")
        from zaza.tools.options.flow import register
        mcp = MagicMock()
        tools: dict[str, Any] = {}
        mcp.tool.return_value = lambda fn: tools.update({fn.__name__: fn}) or fn
        register(mcp, mock_yf, mock_cache)

        result = json.loads(await tools["get_options_flow"]("AAPL"))
        assert "error" in result
