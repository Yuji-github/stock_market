# create the docker production when I create the project as a placeholder of dependencies
# STAGE 1: Builder
FROM python:3.11-slim as builder

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

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies (Production only, no dev deps)
RUN poetry install --no-dev --no-root

# STAGE 2: Runtime (The final image)
FROM python:3.11-slim as runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Add the virtual env to PATH so we don't need to prefix 'python'
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create a non-root user for security
RUN addgroup --system appgroup && adduser --system --group appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src /app/src

# Switch to non-root user
USER appuser

# Entry point
CMD ["python", "src/main.py"]