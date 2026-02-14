# TASK-029: Add Docker Environment Variable Overrides to Config

## Task ID
TASK-029

## Status
COMPLETED

## Title
Add Docker Environment Variable Overrides to Config

## Description
Modify `src/zaza/config.py` to make `CACHE_DIR` and `PKSCREENER_CONTAINER` configurable via environment variables. This is the **only production code change** required to support Docker containerization.

In Docker, the cache must live at `/cache` (mapped to a named volume) instead of `~/.zaza/cache/`, and the PKScreener container name may differ from the default `pkscreener`. Adding env var overrides with fallback to existing defaults ensures non-Docker usage is completely unaffected.

## Acceptance Criteria

### Functional Requirements
- [ ] `CACHE_DIR` reads from `ZAZA_CACHE_DIR` env var, falls back to `~/.zaza/cache/` if unset
- [ ] `PREDICTIONS_DIR` derives from `CACHE_DIR` (i.e., `CACHE_DIR / "predictions"`)
- [ ] `PKSCREENER_CONTAINER` reads from `PKSCREENER_CONTAINER` env var, falls back to `"pkscreener"` if unset
- [ ] Existing behavior is completely unchanged when env vars are not set
- [ ] All downstream code using `CACHE_DIR`, `PREDICTIONS_DIR`, and `PKSCREENER_CONTAINER` works without modification

### Non-Functional Requirements
- [ ] **Testing**: Unit tests verify env var override behavior (set var → check value, unset → check default)
- [ ] **Testing**: Existing config tests continue to pass
- [ ] **Security**: No secrets or default credentials introduced
- [ ] **Documentation**: Inline comments explaining the env var override pattern

## Dependencies
- TASK-002: Configuration module (must exist to modify)

## Technical Notes

### Code Change

In `src/zaza/config.py`, change these two lines:

**Before:**
```python
CACHE_DIR = Path.home() / ".zaza" / "cache"
PKSCREENER_CONTAINER = "pkscreener"
```

**After:**
```python
CACHE_DIR = Path(os.getenv("ZAZA_CACHE_DIR", str(Path.home() / ".zaza" / "cache")))
PKSCREENER_CONTAINER = os.getenv("PKSCREENER_CONTAINER", "pkscreener")
```

`PREDICTIONS_DIR` already derives from `CACHE_DIR` so it automatically picks up the override:
```python
PREDICTIONS_DIR = CACHE_DIR / "predictions"
```

### Test Cases

```python
def test_cache_dir_default(monkeypatch):
    """CACHE_DIR defaults to ~/.zaza/cache/ when env var is unset."""
    monkeypatch.delenv("ZAZA_CACHE_DIR", raising=False)
    # Re-import or reload config
    assert config.CACHE_DIR == Path.home() / ".zaza" / "cache"

def test_cache_dir_override(monkeypatch):
    """CACHE_DIR uses ZAZA_CACHE_DIR when set."""
    monkeypatch.setenv("ZAZA_CACHE_DIR", "/cache")
    # Re-import or reload config
    assert config.CACHE_DIR == Path("/cache")

def test_predictions_dir_follows_cache_dir(monkeypatch):
    """PREDICTIONS_DIR is always CACHE_DIR / predictions."""
    monkeypatch.setenv("ZAZA_CACHE_DIR", "/tmp/test-cache")
    # Re-import or reload config
    assert config.PREDICTIONS_DIR == Path("/tmp/test-cache/predictions")

def test_pkscreener_container_default(monkeypatch):
    """PKSCREENER_CONTAINER defaults to 'pkscreener'."""
    monkeypatch.delenv("PKSCREENER_CONTAINER", raising=False)
    assert config.PKSCREENER_CONTAINER == "pkscreener"

def test_pkscreener_container_override(monkeypatch):
    """PKSCREENER_CONTAINER uses env var when set."""
    monkeypatch.setenv("PKSCREENER_CONTAINER", "my-pkscreener")
    assert config.PKSCREENER_CONTAINER == "my-pkscreener"
```

### Implementation Hints
1. Since `CACHE_DIR` and `PREDICTIONS_DIR` are set at module import time, tests need `importlib.reload(config)` after setting env vars via `monkeypatch`
2. `os.getenv` returns `str`, so wrap in `Path()` for `CACHE_DIR`
3. This is a 2-line change — resist the temptation to refactor more

## Estimated Complexity
**Small** (1-2 hours)

## References
- doc/DOCKER-PLAN.md Section 1 (Code Change)
- ZAZA_ARCHITECTURE.md Section 13 (Configuration & Setup)
