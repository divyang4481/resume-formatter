# Use a python 3.11 base image suitable for cloud environments
FROM python:3.11-slim as builder

# Define environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.0.0 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_HOME="/opt/poetry"

ENV PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies (including potential requirements for local parsers like tika)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install core dependencies.
# In CI/CD pipelines targeting specific clouds, you would add `--extras "aws"` or `--extras "azure"` here.
ARG EXTRA_DEPENDENCIES=""
RUN if [ -z "$EXTRA_DEPENDENCIES" ]; then \
      poetry install --no-root --only main; \
    else \
      poetry install --no-root --only main --extras "$EXTRA_DEPENDENCIES"; \
    fi

FROM python:3.11-slim as runtime

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy the application code
COPY ./app /app/app
COPY ./config /app/config
COPY ./templates /app/templates
COPY ./policies /app/policies

# Expose FastAPI port
EXPOSE 8000

# Start the FastAPI server (suitable for ECS, Cloud Run, Azure Container Apps)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
