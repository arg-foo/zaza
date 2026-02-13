"""Wrapper around yfinance providing cached access to Yahoo Finance data."""

from __future__ import annotations

from typing import Any

import pandas as pd
import structlog
import yfinance as yf

from zaza.cache.store import FileCache

logger = structlog.get_logger(__name__)


class YFinanceClient:
    """Cached yfinance client for market data and fundamentals."""

    def __init__(self, cache: FileCache) -> None:
        self.cache = cache

    @staticmethod
    def _df_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
        """Convert a DataFrame to a list of dicts, handling None/empty."""
        if df is None or df.empty:
            return []
        df = df.reset_index()
        # Convert Timestamps to strings for JSON serialization
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype(str)
        return df.to_dict(orient="records")

    def get_quote(self, ticker: str) -> dict[str, Any]:
        """Get current quote data (price, volume, market cap, etc.)."""
        cache_key = self.cache.make_key("quote", ticker=ticker)
        cached = self.cache.get(cache_key, "prices")
        if cached is not None:
            return cached
        try:
            info = yf.Ticker(ticker).info
            if not info or "regularMarketPrice" not in info:
                return {}
            self.cache.set(cache_key, "prices", info)
            return info
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return {}

    def get_history(
        self,
        ticker: str,
        period: str = "6mo",
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        """Get historical OHLCV data."""
        cache_key = self.cache.make_key(
            "history",
            ticker=ticker,
            period=period,
            start=start,
            end=end,
            interval=interval,
        )
        cached = self.cache.get(cache_key, "prices")
        if cached is not None:
            return cached
        try:
            t = yf.Ticker(ticker)
            if start and end:
                df = t.history(start=start, end=end, interval=interval)
            else:
                df = t.history(period=period, interval=interval)
            records = self._df_to_records(df)
            if records:
                self.cache.set(cache_key, "prices", records)
            return records
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return []

    def get_financials(self, ticker: str, period: str = "annual") -> dict[str, Any]:
        """Get financial statements (income, balance sheet, cash flow)."""
        cache_key = self.cache.make_key("financials", ticker=ticker, period=period)
        cached = self.cache.get(cache_key, "fundamentals")
        if cached is not None:
            return cached
        try:
            t = yf.Ticker(ticker)
            if period == "quarterly":
                income = self._df_to_records(
                    t.quarterly_financials.T
                    if t.quarterly_financials is not None
                    else None
                )
                balance = self._df_to_records(
                    t.quarterly_balance_sheet.T
                    if t.quarterly_balance_sheet is not None
                    else None
                )
                cashflow = self._df_to_records(
                    t.quarterly_cashflow.T
                    if t.quarterly_cashflow is not None
                    else None
                )
            else:
                income = self._df_to_records(
                    t.financials.T if t.financials is not None else None
                )
                balance = self._df_to_records(
                    t.balance_sheet.T if t.balance_sheet is not None else None
                )
                cashflow = self._df_to_records(
                    t.cashflow.T if t.cashflow is not None else None
                )
            result = {
                "income_statement": income,
                "balance_sheet": balance,
                "cash_flow": cashflow,
            }
            self.cache.set(cache_key, "fundamentals", result)
            return result
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return {"income_statement": [], "balance_sheet": [], "cash_flow": []}

    def get_options_expirations(self, ticker: str) -> list[str]:
        """Get available options expiration dates."""
        cache_key = self.cache.make_key("options_exp", ticker=ticker)
        cached = self.cache.get(cache_key, "options_chain")
        if cached is not None:
            return cached
        try:
            dates = list(yf.Ticker(ticker).options)
            self.cache.set(cache_key, "options_chain", dates)
            return dates
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return []

    def get_options_chain(self, ticker: str, date: str) -> dict[str, Any]:
        """Get options chain for a specific expiry date."""
        cache_key = self.cache.make_key("options_chain", ticker=ticker, date=date)
        cached = self.cache.get(cache_key, "options_chain")
        if cached is not None:
            return cached
        try:
            chain = yf.Ticker(ticker).option_chain(date)
            result = {
                "calls": self._df_to_records(chain.calls),
                "puts": self._df_to_records(chain.puts),
            }
            self.cache.set(cache_key, "options_chain", result)
            return result
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return {"calls": [], "puts": []}

    def get_insider_transactions(self, ticker: str) -> list[dict[str, Any]]:
        """Get insider transactions."""
        cache_key = self.cache.make_key("insider_tx", ticker=ticker)
        cached = self.cache.get(cache_key, "insider_sentiment")
        if cached is not None:
            return cached
        try:
            t = yf.Ticker(ticker)
            df = t.insider_transactions
            records = self._df_to_records(df)
            self.cache.set(cache_key, "insider_sentiment", records)
            return records
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return []

    def get_institutional_holders(self, ticker: str) -> dict[str, Any]:
        """Get institutional holders data."""
        cache_key = self.cache.make_key("inst_holders", ticker=ticker)
        cached = self.cache.get(cache_key, "institutional_holdings")
        if cached is not None:
            return cached
        try:
            t = yf.Ticker(ticker)
            holders = self._df_to_records(t.institutional_holders)
            major = self._df_to_records(t.major_holders)
            result = {"institutional_holders": holders, "major_holders": major}
            self.cache.set(cache_key, "institutional_holdings", result)
            return result
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return {"institutional_holders": [], "major_holders": []}

    def get_earnings(self, ticker: str) -> dict[str, Any]:
        """Get earnings history and dates."""
        cache_key = self.cache.make_key("earnings", ticker=ticker)
        cached = self.cache.get(cache_key, "earnings_history")
        if cached is not None:
            return cached
        try:
            t = yf.Ticker(ticker)
            earnings = self._df_to_records(t.earnings_history)
            calendar: dict[str, Any] = {}
            try:
                cal = t.calendar
                if isinstance(cal, pd.DataFrame):
                    calendar = cal.to_dict()
                elif isinstance(cal, dict):
                    calendar = cal
            except Exception:
                pass
            result: dict[str, Any] = {
                "earnings_history": earnings,
                "calendar": calendar,
            }
            self.cache.set(cache_key, "earnings_history", result)
            return result
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return {"earnings_history": [], "calendar": {}}

    def get_news(self, ticker: str) -> list[dict[str, Any]]:
        """Get recent news articles."""
        cache_key = self.cache.make_key("news", ticker=ticker)
        cached = self.cache.get(cache_key, "news_sentiment")
        if cached is not None:
            return cached
        try:
            news = yf.Ticker(ticker).news
            if not news:
                return []
            self.cache.set(cache_key, "news_sentiment", news)
            return news
        except Exception as e:
            logger.warning("yfinance_error", ticker=ticker, error=str(e))
            return []
