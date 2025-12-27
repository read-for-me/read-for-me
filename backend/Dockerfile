# ==============================================================================
# Read-For-Me Backend Dockerfile
# ==============================================================================
# Multi-stage build for optimized production image
# - Stage 1: Build dependencies with uv
# - Stage 2: Production runtime with minimal footprint
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first (for better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies (without dev dependencies)
RUN uv sync --frozen --no-install-project --no-dev

# ------------------------------------------------------------------------------
# Stage 2: Runtime - Production image
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Install system dependencies for:
# - playwright (chromium): libnss3, libatk1.0, etc.
# - audio processing (pydub): ffmpeg
# - general: curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    # Playwright/Chromium dependencies
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser prompts/ ./prompts/
COPY --chown=appuser:appuser output_schemas/ ./output_schemas/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Playwright browsers (Chromium only for smaller image)
# Note: Must run after venv is in PATH
RUN playwright install chromium

# Switch to non-root user
USER appuser

# Cloud Run uses PORT env var (default: 8080)
ENV PORT=8080
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the application
# Cloud Run automatically sets PORT environment variable
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

