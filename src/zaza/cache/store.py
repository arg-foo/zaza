"""File-based cache with TTL per data category."""

import json
import re
import time
from pathlib import Path

import structlog

from zaza.config import CACHE_DIR, CACHE_TTL

logger = structlog.get_logger(__name__)


class FileCache:
    """SQLite-free file-based cache storing JSON responses with TTL."""

    def __init__(self, cache_dir: Path = CACHE_DIR) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def make_key(endpoint: str, **params: object) -> str:
        """Generate a deterministic, filesystem-safe cache key."""
        parts = [endpoint]
        for k in sorted(params.keys()):
            v = params[k]
            if v is not None:
                parts.append(str(v))
        key = "__".join(parts)
        # Sanitize for filesystem safety
        return re.sub(r'[^\w\-.]', '_', key)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str, category: str) -> dict | list | None:
        """Return cached data if TTL is valid, None otherwise."""
        path = self._path(key)
        if not path.exists():
            logger.debug("cache_miss", key=key, reason="not_found")
            return None
        try:
            raw = json.loads(path.read_text())
            ttl = CACHE_TTL.get(category, 3600)
            if time.time() - raw["cached_at"] > ttl:
                path.unlink(missing_ok=True)
                logger.debug("cache_miss", key=key, reason="expired")
                return None
            logger.debug("cache_hit", key=key, category=category)
            return raw["data"]
        except (json.JSONDecodeError, KeyError, OSError):
            path.unlink(missing_ok=True)
            logger.warning("cache_corrupt", key=key)
            return None

    def set(self, key: str, category: str, data: dict | list) -> None:
        """Write data to cache."""
        path = self._path(key)
        payload = {"cached_at": time.time(), "category": category, "data": data}
        try:
            path.write_text(json.dumps(payload, default=str))
            logger.debug("cache_set", key=key, category=category)
        except OSError:
            logger.warning("cache_write_failed", key=key)

    def invalidate(self, key: str) -> None:
        """Remove a specific cache entry."""
        path = self._path(key)
        path.unlink(missing_ok=True)

    def clear(self, category: str | None = None) -> int:
        """Clear all cache or a specific category. Returns count of removed files."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            if category is None:
                path.unlink(missing_ok=True)
                count += 1
            else:
                try:
                    raw = json.loads(path.read_text())
                    if raw.get("category") == category:
                        path.unlink(missing_ok=True)
                        count += 1
                except (json.JSONDecodeError, KeyError, OSError):
                    pass
        return count
