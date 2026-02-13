# ============================================================
# Zaza MCP Server — Multi-Stage Dockerfile
# ============================================================
# Stages:
#   1. deps      — Install Python dependencies with uv
#   2. playwright — Install Chromium browser for browser tools
#   3. runtime   — Final production image
#   4. dev       — Development image with test dependencies
# ============================================================

# ----------------------------------------------------------
# Stage 1: Install Python dependencies
# ----------------------------------------------------------
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first for layer caching —
# expensive dep install is cached when only src/ changes
COPY pyproject.toml uv.lock ./

# Optional: set BUILD_PROPHET=1 to include Prophet forecasting
ARG BUILD_PROPHET=0
RUN if [ "$BUILD_PROPHET" = "1" ]; then \
      uv sync --frozen --no-dev --extra forecast; \
    else \
      uv sync --frozen --no-dev; \
    fi

# ----------------------------------------------------------
# Stage 2: Install Playwright Chromium
# ----------------------------------------------------------
FROM deps AS playwright

RUN uv run playwright install-deps chromium \
 && uv run playwright install chromium

# ----------------------------------------------------------
# Stage 3: Runtime image
# ----------------------------------------------------------
FROM python:3.12-slim AS runtime

# Chromium runtime libs + Docker CLI for PKScreener docker exec
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libx11-6 libx11-xcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxfixes3 libxi6 libxrandr2 libxrender1 \
    libxtst6 libglib2.0-0 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libpango-1.0-0 \
    libcairo2 fonts-liberation libxss1 docker.io \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python venv from deps stage
COPY --from=deps /app/.venv /app/.venv
# Copy Playwright browsers from playwright stage
COPY --from=playwright /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy application code
COPY src/ src/

# Activate venv via PATH
ENV PATH="/app/.venv/bin:$PATH"
# Unbuffered output — critical for MCP JSON-RPC over stdin/stdout
ENV PYTHONUNBUFFERED=1
# Docker cache path (overrides ~/.zaza/cache/ default)
ENV ZAZA_CACHE_DIR=/cache

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "zaza.server"]

# ----------------------------------------------------------
# Stage 4: Development image (extends runtime)
# ----------------------------------------------------------
FROM runtime AS dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY tests/ tests/
CMD ["python", "-m", "pytest", "tests/"]
