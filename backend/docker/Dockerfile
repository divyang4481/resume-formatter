# Use the pre-built base image as a builder to extract the compiled environment
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} as builder

# Create a clean, minimal runtime image
FROM --platform=linux/amd64 python:3.11-slim as runtime

RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    SENTENCE_TRANSFORMERS_HOME="/app/.cache"

# Copy ONLY the virtual environment and cached models from the heavy base image
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.cache /app/.cache

# QUICK FIX: Install the missing database driver here
RUN pip install psycopg2-binary==2.9.9

# Copy the application code (This is the only part that changes often)
COPY ./app /app/app
COPY ./config /app/config
COPY ./templates /app/templates
COPY ./policies /app/policies

# Expose FastAPI port
EXPOSE 8000

# Start the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]




