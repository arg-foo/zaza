"""Configuration for the trade execution consumer."""

from __future__ import annotations

import os
from dataclasses import dataclass

import structlog

log = structlog.get_logger()


@dataclass
class ConsumerSettings:
    """Settings for the Redis stream consumer and order executor."""

    redis_url: str
    tiger_mcp_url: str
    zaza_mcp_url: str

    redis_stream_prefix: str = "tiger:events"
    consumer_group: str = "trade-executor"
    consumer_name: str = "executor-1"

    rth_open_hour: int = 9
    rth_open_minute: int = 30
    rth_close_hour: int = 16
    rth_close_minute: int = 0

    rth_scan_interval_seconds: int = 300
    order_delay_ms: int = 500
    xread_block_ms: int = 5000
    xread_count: int = 10

    def __post_init__(self) -> None:
        if not self.redis_url:
            raise ValueError("redis_url must be non-empty")
        if not self.tiger_mcp_url:
            raise ValueError("tiger_mcp_url must be non-empty")
        if not self.zaza_mcp_url:
            raise ValueError("zaza_mcp_url must be non-empty")
        if self.xread_block_ms <= 0:
            raise ValueError("xread_block_ms must be positive")
        if self.xread_count <= 0:
            raise ValueError("xread_count must be positive")
        if self.order_delay_ms < 0:
            raise ValueError("order_delay_ms must be non-negative")
        if self.rth_scan_interval_seconds <= 0:
            raise ValueError("rth_scan_interval_seconds must be positive")

    @property
    def transaction_stream(self) -> str:
        return f"{self.redis_stream_prefix}:transaction"

    @classmethod
    def from_env(cls) -> ConsumerSettings:
        """Build settings from environment variables.

        Required: REDIS_URL, TIGER_MCP_URL, ZAZA_MCP_URL.
        Optional vars fall back to dataclass defaults.
        """
        redis_url = os.environ.get("REDIS_URL", "")
        if not redis_url:
            raise ValueError("REDIS_URL environment variable is required")

        tiger_mcp_url = os.environ.get("TIGER_MCP_URL", "")
        if not tiger_mcp_url:
            raise ValueError("TIGER_MCP_URL environment variable is required")

        zaza_mcp_url = os.environ.get("ZAZA_MCP_URL", "")
        if not zaza_mcp_url:
            raise ValueError("ZAZA_MCP_URL environment variable is required")

        return cls(
            redis_url=redis_url,
            tiger_mcp_url=tiger_mcp_url,
            zaza_mcp_url=zaza_mcp_url,
            consumer_group=os.environ.get("CONSUMER_GROUP", "trade-executor"),
            consumer_name=os.environ.get("CONSUMER_NAME", "executor-1"),
            rth_scan_interval_seconds=int(os.environ.get("RTH_SCAN_INTERVAL", "300")),
            order_delay_ms=int(os.environ.get("ORDER_DELAY_MS", "500")),
            xread_block_ms=int(os.environ.get("XREAD_BLOCK_MS", "5000")),
            xread_count=int(os.environ.get("XREAD_COUNT", "10")),
        )
