"""Redis stream consumer for Tiger broker transaction events."""

from __future__ import annotations

import asyncio
import signal
from typing import Any, Awaitable, Callable

import orjson
import structlog
from redis.asyncio import Redis

from zaza.consumer.config import ConsumerSettings

logger = structlog.get_logger(__name__)


async def consume_stream(
    settings: ConsumerSettings,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Main consumer loop. Connects to Redis, creates consumer group, processes messages.

    Steps:
    1. Connect to Redis
    2. Create consumer group if not exists (XGROUP CREATE ... 0 MKSTREAM)
    3. Process pending (unACKed) messages first (crash recovery) using "0" as ID
    4. Then read new messages using ">" as ID
    5. For each message: deserialize, call handler, XACK on success
    6. Graceful shutdown on SIGTERM/SIGINT
    """
    redis = Redis.from_url(settings.redis_url, decode_responses=False)
    stream_key = settings.transaction_stream
    group = settings.consumer_group
    consumer = settings.consumer_name

    shutdown = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("shutdown_signal_received")
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        # Create consumer group (ignore if exists)
        try:
            await redis.xgroup_create(stream_key, group, id="0", mkstream=True)
            logger.info("consumer_group_created", group=group, stream=stream_key)
        except Exception:
            # Group already exists
            logger.debug("consumer_group_exists", group=group)

        # Phase 1: Process pending (unACKed) messages
        logger.info("processing_pending_messages")
        await _read_and_process(
            redis,
            stream_key,
            group,
            consumer,
            settings,
            handler,
            read_id="0",
            shutdown=shutdown,
        )

        # Phase 2: Process new messages
        logger.info("processing_new_messages")
        await _read_and_process(
            redis,
            stream_key,
            group,
            consumer,
            settings,
            handler,
            read_id=">",
            shutdown=shutdown,
        )
    finally:
        await redis.aclose()
        logger.info("consumer_stopped")


async def _read_and_process(
    redis: Redis,
    stream_key: str,
    group: str,
    consumer: str,
    settings: ConsumerSettings,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
    read_id: str,
    shutdown: asyncio.Event,
) -> None:
    """Read messages from stream and process them.

    Args:
        read_id: "0" for pending messages, ">" for new messages.
    """
    while not shutdown.is_set():
        try:
            results = await redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream_key: read_id},
                count=settings.xread_count,
                block=settings.xread_block_ms,
            )
        except Exception as exc:
            logger.error("xreadgroup_error", error=str(exc))
            await asyncio.sleep(1)
            continue

        if not results:
            if read_id == "0":
                # No more pending messages
                return
            continue

        for _stream_name, messages in results:
            for msg_id, fields in messages:
                if read_id == "0" and not fields:
                    # Pending message already delivered but empty -- skip
                    return

                try:
                    # Fields is a dict of bytes->bytes
                    # We expect a "data" field with JSON
                    raw = fields.get(b"data", b"{}")
                    event = orjson.loads(raw)
                    await handler(event)
                    await redis.xack(stream_key, group, msg_id)
                    logger.debug("message_processed", msg_id=msg_id)
                except Exception as exc:
                    logger.error(
                        "message_handler_error",
                        msg_id=msg_id,
                        error=str(exc),
                        exc_info=True,
                    )
