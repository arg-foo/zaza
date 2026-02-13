"""Centralized configuration for the Zaza MCP server."""

import os
from pathlib import Path

# Directories
# Docker override: set ZAZA_CACHE_DIR to change cache location (e.g., /cache in Docker)
CACHE_DIR = Path(os.getenv("ZAZA_CACHE_DIR", str(Path.home() / ".zaza" / "cache")))
PREDICTIONS_DIR = CACHE_DIR / "predictions"

# PKScreener Docker
# Docker override: set PKSCREENER_CONTAINER to change the PKScreener container name
PKSCREENER_CONTAINER = os.getenv("PKSCREENER_CONTAINER", "pkscreener")

# SEC EDGAR
EDGAR_USER_AGENT = "Zaza/1.0 (zaza-mcp@example.com)"

# Cache TTLs (seconds)
CACHE_TTL: dict[str, int] = {
    "prices": 3600,
    "fundamentals": 86400,
    "filings_meta": 86400,
    "company_facts": 604800,
    "options_chain": 1800,
    "implied_vol": 1800,
    "news_sentiment": 7200,
    "social_sentiment": 3600,
    "insider_sentiment": 86400,
    "fear_greed": 14400,
    "treasury_yields": 3600,
    "market_indices": 3600,
    "commodities": 3600,
    "economic_calendar": 86400,
    "correlations": 21600,
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


def _ensure_dirs() -> None:
    """Create cache directories if they don't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)


_ensure_dirs()


def get_reddit_client_id() -> str | None:
    """Get Reddit client ID from environment."""
    return os.getenv("REDDIT_CLIENT_ID") or None


def get_reddit_client_secret() -> str | None:
    """Get Reddit client secret from environment."""
    return os.getenv("REDDIT_CLIENT_SECRET") or None


def get_fred_api_key() -> str | None:
    """Get FRED API key from environment."""
    return os.getenv("FRED_API_KEY") or None


def has_reddit_credentials() -> bool:
    """Check if Reddit API credentials are configured."""
    return bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"))


def has_fred_key() -> bool:
    """Check if FRED API key is configured."""
    return bool(os.getenv("FRED_API_KEY"))
