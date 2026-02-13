# TASK-003: File-Based Cache System

## Task ID
TASK-003

## Status
PENDING

## Title
Implement File-Based Cache System

## Description
Implement `src/zaza/cache/store.py` — a file-based response cache that stores API responses as JSON files in `~/.zaza/cache/` with configurable TTL per data category. This cache prevents duplicate API calls both within a session and across Claude Code sessions.

Every API client and tool checks the cache before making external calls. The cache key is derived from the endpoint name + parameters.

## Acceptance Criteria

### Functional Requirements
- [ ] `FileCache` class implemented in `src/zaza/cache/store.py`
- [ ] `get(key: str, category: str) -> dict | None` — returns cached data if TTL valid, None if expired/missing
- [ ] `set(key: str, category: str, data: dict) -> None` — writes data to cache file
- [ ] `make_key(endpoint: str, **params) -> str` — generates deterministic cache key from endpoint + params
- [ ] Cache files stored as JSON in `~/.zaza/cache/` with pattern: `{endpoint}__{param1}__{param2}.json`
- [ ] Each cache file includes metadata: `{"cached_at": timestamp, "data": ...}`
- [ ] TTL lookup uses category → `config.CACHE_TTL[category]`
- [ ] `invalidate(key: str) -> None` — removes a specific cache entry
- [ ] `clear(category: str | None = None) -> None` — clears all cache or a specific category
- [ ] Handles corrupt/unreadable cache files gracefully (delete and return None)

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with mocked filesystem; test TTL expiry, cache hit, cache miss, corrupt file handling
- [ ] **Performance**: File I/O should be minimal — single read/write per operation
- [ ] **Reliability**: Never raise on cache errors — always fall through to API call
- [ ] **Security**: Cache files contain only public market data, no credentials

## Dependencies
- TASK-001: Project scaffolding
- TASK-002: Configuration module (for CACHE_DIR, CACHE_TTL)

## Technical Notes

### Cache Key Format
```python
def make_key(endpoint: str, **params) -> str:
    parts = [endpoint]
    for k in sorted(params.keys()):
        v = params[k]
        if v is not None:
            parts.append(str(v))
    return "__".join(parts)
# Example: make_key("get_prices", ticker="AAPL", start="2024-01-01", end="2024-12-31")
# → "get_prices__AAPL__2024-01-01__2024-12-31"
```

### Cache File Structure
```json
{
    "cached_at": 1705000000.0,
    "category": "prices",
    "data": { ... }
}
```

### FileCache Class
```python
import json
import time
from pathlib import Path
from zaza.config import CACHE_DIR, CACHE_TTL

class FileCache:
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str, category: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            ttl = CACHE_TTL.get(category, 3600)
            if time.time() - raw["cached_at"] > ttl:
                path.unlink(missing_ok=True)
                return None
            return raw["data"]
        except (json.JSONDecodeError, KeyError, OSError):
            path.unlink(missing_ok=True)
            return None

    def set(self, key: str, category: str, data: dict) -> None:
        path = self._path(key)
        payload = {"cached_at": time.time(), "category": category, "data": data}
        path.write_text(json.dumps(payload, default=str))
```

### Implementation Hints
1. Use `default=str` in `json.dumps` to handle datetime and Decimal objects from yfinance
2. Cache keys must be filesystem-safe — sanitize any special characters
3. The predictions directory (`~/.zaza/cache/predictions/`) is append-only and NOT managed by this cache (TASK-022 handles it)
4. Consider adding a `stats()` method for debugging (total files, size, hits/misses)

## Estimated Complexity
**Small** (2-3 hours)

## References
- ZAZA_ARCHITECTURE.md Section 9.2 (File-Based Response Cache)
