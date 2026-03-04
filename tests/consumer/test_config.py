"""Tests for consumer configuration module."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from zaza.consumer.config import ConsumerSettings


class TestConsumerSettingsDefaults:
    """Verify default field values are applied correctly."""

    def test_defaults_applied(self) -> None:
        settings = ConsumerSettings(
            redis_url="redis://localhost:6379/0",
            tiger_mcp_url="http://localhost:8000/mcp",
            zaza_mcp_url="http://localhost:8100/mcp",
        )
        assert settings.redis_stream_prefix == "tiger:events"
        assert settings.consumer_group == "trade-executor"
        assert settings.consumer_name == "executor-1"
        assert settings.rth_open_hour == 9
        assert settings.rth_open_minute == 30
        assert settings.rth_close_hour == 16
        assert settings.rth_close_minute == 0
        assert settings.rth_scan_interval_seconds == 300
        assert settings.order_delay_ms == 500
        assert settings.xread_block_ms == 5000
        assert settings.xread_count == 10


class TestConsumerSettingsExplicitValues:
    """Verify explicit values override defaults."""

    def test_all_fields_explicit(self) -> None:
        settings = ConsumerSettings(
            redis_url="redis://myhost:6380/1",
            redis_stream_prefix="custom:prefix",
            consumer_group="my-group",
            consumer_name="worker-7",
            tiger_mcp_url="http://tiger:9000/mcp",
            zaza_mcp_url="http://zaza:9100/mcp",
            rth_open_hour=10,
            rth_open_minute=0,
            rth_close_hour=15,
            rth_close_minute=45,
            rth_scan_interval_seconds=60,
            order_delay_ms=1000,
            xread_block_ms=2000,
            xread_count=50,
        )
        assert settings.redis_url == "redis://myhost:6380/1"
        assert settings.redis_stream_prefix == "custom:prefix"
        assert settings.consumer_group == "my-group"
        assert settings.consumer_name == "worker-7"
        assert settings.tiger_mcp_url == "http://tiger:9000/mcp"
        assert settings.zaza_mcp_url == "http://zaza:9100/mcp"
        assert settings.rth_open_hour == 10
        assert settings.rth_open_minute == 0
        assert settings.rth_close_hour == 15
        assert settings.rth_close_minute == 45
        assert settings.rth_scan_interval_seconds == 60
        assert settings.order_delay_ms == 1000
        assert settings.xread_block_ms == 2000
        assert settings.xread_count == 50


class TestConsumerSettingsValidation:
    """Verify __post_init__ validation rejects invalid inputs."""

    def test_empty_redis_url_raises(self) -> None:
        with pytest.raises(ValueError, match="redis_url"):
            ConsumerSettings(
                redis_url="",
                tiger_mcp_url="http://localhost:8000/mcp",
                zaza_mcp_url="http://localhost:8100/mcp",
            )

    def test_empty_tiger_mcp_url_raises(self) -> None:
        with pytest.raises(ValueError, match="tiger_mcp_url"):
            ConsumerSettings(
                redis_url="redis://localhost:6379/0",
                tiger_mcp_url="",
                zaza_mcp_url="http://localhost:8100/mcp",
            )

    def test_empty_zaza_mcp_url_raises(self) -> None:
        with pytest.raises(ValueError, match="zaza_mcp_url"):
            ConsumerSettings(
                redis_url="redis://localhost:6379/0",
                tiger_mcp_url="http://localhost:8000/mcp",
                zaza_mcp_url="",
            )

    def test_negative_xread_block_ms_raises(self) -> None:
        with pytest.raises(ValueError, match="xread_block_ms"):
            ConsumerSettings(
                redis_url="redis://localhost:6379/0",
                tiger_mcp_url="http://localhost:8000/mcp",
                zaza_mcp_url="http://localhost:8100/mcp",
                xread_block_ms=-1,
            )

    def test_zero_xread_block_ms_raises(self) -> None:
        with pytest.raises(ValueError, match="xread_block_ms"):
            ConsumerSettings(
                redis_url="redis://localhost:6379/0",
                tiger_mcp_url="http://localhost:8000/mcp",
                zaza_mcp_url="http://localhost:8100/mcp",
                xread_block_ms=0,
            )

    def test_negative_xread_count_raises(self) -> None:
        with pytest.raises(ValueError, match="xread_count"):
            ConsumerSettings(
                redis_url="redis://localhost:6379/0",
                tiger_mcp_url="http://localhost:8000/mcp",
                zaza_mcp_url="http://localhost:8100/mcp",
                xread_count=-5,
            )

    def test_zero_xread_count_raises(self) -> None:
        with pytest.raises(ValueError, match="xread_count"):
            ConsumerSettings(
                redis_url="redis://localhost:6379/0",
                tiger_mcp_url="http://localhost:8000/mcp",
                zaza_mcp_url="http://localhost:8100/mcp",
                xread_count=0,
            )

    def test_negative_order_delay_ms_raises(self) -> None:
        with pytest.raises(ValueError, match="order_delay_ms"):
            ConsumerSettings(
                redis_url="redis://localhost:6379/0",
                tiger_mcp_url="http://localhost:8000/mcp",
                zaza_mcp_url="http://localhost:8100/mcp",
                order_delay_ms=-1,
            )

    def test_zero_order_delay_ms_allowed(self) -> None:
        settings = ConsumerSettings(
            redis_url="redis://localhost:6379/0",
            tiger_mcp_url="http://localhost:8000/mcp",
            zaza_mcp_url="http://localhost:8100/mcp",
            order_delay_ms=0,
        )
        assert settings.order_delay_ms == 0

    def test_negative_rth_scan_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="rth_scan_interval_seconds"):
            ConsumerSettings(
                redis_url="redis://localhost:6379/0",
                tiger_mcp_url="http://localhost:8000/mcp",
                zaza_mcp_url="http://localhost:8100/mcp",
                rth_scan_interval_seconds=0,
            )


class TestTransactionStream:
    """Verify the transaction_stream property."""

    def test_default_prefix(self) -> None:
        settings = ConsumerSettings(
            redis_url="redis://localhost:6379/0",
            tiger_mcp_url="http://localhost:8000/mcp",
            zaza_mcp_url="http://localhost:8100/mcp",
        )
        assert settings.transaction_stream == "tiger:events:transaction"

    def test_custom_prefix(self) -> None:
        settings = ConsumerSettings(
            redis_url="redis://localhost:6379/0",
            tiger_mcp_url="http://localhost:8000/mcp",
            zaza_mcp_url="http://localhost:8100/mcp",
            redis_stream_prefix="prod:streams",
        )
        assert settings.transaction_stream == "prod:streams:transaction"


class TestFromEnv:
    """Verify from_env() classmethod reads environment variables."""

    @staticmethod
    def _required_env() -> dict[str, str]:
        return {
            "REDIS_URL": "redis://envhost:6379/2",
            "TIGER_MCP_URL": "http://tiger-env:8000/mcp",
            "ZAZA_MCP_URL": "http://zaza-env:8100/mcp",
        }

    def test_from_env_required_only(self) -> None:
        env = self._required_env()
        with patch.dict(os.environ, env, clear=True):
            settings = ConsumerSettings.from_env()

        assert settings.redis_url == "redis://envhost:6379/2"
        assert settings.tiger_mcp_url == "http://tiger-env:8000/mcp"
        assert settings.zaza_mcp_url == "http://zaza-env:8100/mcp"
        # Defaults
        assert settings.consumer_group == "trade-executor"
        assert settings.consumer_name == "executor-1"
        assert settings.rth_scan_interval_seconds == 300
        assert settings.order_delay_ms == 500
        assert settings.xread_block_ms == 5000
        assert settings.xread_count == 10

    def test_from_env_all_overrides(self) -> None:
        env = {
            **self._required_env(),
            "CONSUMER_GROUP": "custom-group",
            "CONSUMER_NAME": "worker-3",
            "RTH_SCAN_INTERVAL": "120",
            "ORDER_DELAY_MS": "250",
            "XREAD_BLOCK_MS": "3000",
            "XREAD_COUNT": "20",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = ConsumerSettings.from_env()

        assert settings.consumer_group == "custom-group"
        assert settings.consumer_name == "worker-3"
        assert settings.rth_scan_interval_seconds == 120
        assert settings.order_delay_ms == 250
        assert settings.xread_block_ms == 3000
        assert settings.xread_count == 20

    def test_from_env_missing_redis_url(self) -> None:
        env = {
            "TIGER_MCP_URL": "http://localhost:8000/mcp",
            "ZAZA_MCP_URL": "http://localhost:8100/mcp",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="REDIS_URL"):
                ConsumerSettings.from_env()

    def test_from_env_missing_tiger_mcp_url(self) -> None:
        env = {
            "REDIS_URL": "redis://localhost:6379/0",
            "ZAZA_MCP_URL": "http://localhost:8100/mcp",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="TIGER_MCP_URL"):
                ConsumerSettings.from_env()

    def test_from_env_missing_zaza_mcp_url(self) -> None:
        env = {
            "REDIS_URL": "redis://localhost:6379/0",
            "TIGER_MCP_URL": "http://localhost:8000/mcp",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="ZAZA_MCP_URL"):
                ConsumerSettings.from_env()
