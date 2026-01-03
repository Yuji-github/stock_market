# Create the docker production when I create the project as a placeholder of dependencies
# STAGE 1: Builder
FROM python:3.12-slim as builder

# Set environment variables for Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system deps required for building python packages (gcc, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

WORKDIR /workspace

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (Production only, no dev deps)
RUN poetry install --without dev --no-root

# STAGE 2: Runtime (The final image)
FROM python:3.12-slim as runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/workspace/.venv/bin:$PATH"

WORKDIR /workspace

# Create a non-root user for security
RUN addgroup --system appgroup && adduser --system --group appuser

# UPDATED: Copy with correct permissions
COPY --from=builder --chown=appuser:appgroup /workspace/.venv /workspace/.venv
COPY --chown=appuser:appgroup src /workspace/src

# Switch to non-root user
USER appuser

# Optional
EXPOSE 8050

# ENTRY POINT
CMD ["python", "src/main.py"]