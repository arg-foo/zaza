# ============================================================
# Zaza Consumer — Dockerfile
# ============================================================
# Lightweight 2-stage build (no Playwright/Chromium).
# ============================================================

# ----------------------------------------------------------
# Stage 1: Install Python dependencies
# ----------------------------------------------------------
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

# ----------------------------------------------------------
# Stage 2: Runtime image
# ----------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
COPY src/ src/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "zaza_consumer"]
