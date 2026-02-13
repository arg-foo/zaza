"""Tests for the configuration module."""

from pathlib import Path
from unittest.mock import patch

from zaza.config import (
    CACHE_DIR,
    CACHE_TTL,
    PREDICTIONS_DIR,
    has_fred_key,
    has_reddit_credentials,
)


def test_cache_dir_is_path() -> None:
    assert isinstance(CACHE_DIR, Path)
    assert str(CACHE_DIR).endswith(".zaza/cache")


def test_predictions_dir_is_path() -> None:
    assert isinstance(PREDICTIONS_DIR, Path)
    assert str(PREDICTIONS_DIR).endswith("predictions")


def test_cache_ttl_has_all_categories() -> None:
    expected_categories = [
        "prices", "fundamentals", "filings_meta", "company_facts",
        "options_chain", "implied_vol", "news_sentiment", "social_sentiment",
        "insider_sentiment", "fear_greed", "treasury_yields", "market_indices",
        "commodities", "economic_calendar", "correlations", "short_interest",
        "institutional_holdings", "fund_flows", "dark_pool", "earnings_history",
        "earnings_calendar", "event_calendar", "buyback_data", "quant_models",
        "backtest_results", "risk_metrics",
    ]
    for cat in expected_categories:
        assert cat in CACHE_TTL, f"Missing cache TTL for {cat}"


def test_cache_ttl_values_are_positive() -> None:
    for category, ttl in CACHE_TTL.items():
        assert ttl > 0, f"TTL for {category} must be positive"


@patch.dict("os.environ", {"REDDIT_CLIENT_ID": "test", "REDDIT_CLIENT_SECRET": "secret"})
def test_has_reddit_credentials_true() -> None:
    assert has_reddit_credentials() is True


@patch.dict("os.environ", {}, clear=True)
def test_has_reddit_credentials_false() -> None:
    assert has_reddit_credentials() is False


@patch.dict("os.environ", {"FRED_API_KEY": "test-key"})
def test_has_fred_key_true() -> None:
    assert has_fred_key() is True


@patch.dict("os.environ", {}, clear=True)
def test_has_fred_key_false() -> None:
    assert has_fred_key() is False
