"""Shared test fixtures for Zaza tests.

Provides reusable fixtures for cache, OHLCV data, and mocked clients
that can be used across all test modules.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from zaza.cache.store import FileCache


@pytest.fixture
def mock_cache(tmp_path: object) -> FileCache:
    """Create a FileCache backed by a temporary directory for test isolation."""
    return FileCache(cache_dir=tmp_path)


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate a deterministic OHLCV DataFrame with 252 business days.

    Uses seed 42 for reproducibility. Prices start at 100 and follow
    a random walk with realistic OHLCV structure.
    """
    rng = np.random.default_rng(42)

    n = 252
    dates = pd.bdate_range(start="2024-01-02", periods=n, freq="B")

    # Random walk for close prices starting at 100
    returns = rng.normal(loc=0.0003, scale=0.015, size=n)
    close = 100.0 * np.cumprod(1 + returns)

    # Derive OHLV from close
    high = close * (1 + rng.uniform(0.001, 0.025, size=n))
    low = close * (1 - rng.uniform(0.001, 0.025, size=n))
    open_ = low + rng.uniform(0.0, 1.0, size=n) * (high - low)
    volume = rng.integers(1_000_000, 50_000_000, size=n)

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume.astype(float),
        },
        index=dates,
    )
    df.index.name = "Date"
    return df


@pytest.fixture
def mock_yf_client(sample_ohlcv: pd.DataFrame, mock_cache: FileCache) -> MagicMock:
    """Create a MagicMock YFinanceClient with pre-configured return values.

    The mock's get_history method returns the sample_ohlcv data converted
    to records format. The mock's get_quote method returns a realistic
    price snapshot.
    """
    client = MagicMock()
    client.cache = mock_cache

    # Convert sample_ohlcv to records format matching YFinanceClient output
    df = sample_ohlcv.reset_index()
    df["Date"] = df["Date"].astype(str)
    records = df.to_dict(orient="records")
    client.get_history.return_value = records

    # Provide a realistic quote snapshot
    last_close = float(sample_ohlcv["Close"].iloc[-1])
    client.get_quote.return_value = {
        "regularMarketPrice": last_close,
        "regularMarketVolume": 15_000_000,
        "marketCap": last_close * 1_000_000_000,
        "shortName": "Test Corp",
        "symbol": "TEST",
    }

    return client
