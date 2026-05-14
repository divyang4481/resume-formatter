# Worker backend image: consumes queue messages and executes document workflows.
# Build context must be the backend/ directory.
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=1000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install the shared library and worker project dependencies. Heavy extraction
# runtimes such as Docling, Torch, and OCR live in parser_service/Dockerfile.
COPY ./common ./common
COPY ./worker_backend ./worker_backend
COPY ./app ./app
COPY ./init_db.py ./init_db.py
RUN pip install --no-cache-dir -e ./common -e ./worker_backend

RUN mkdir -p .data

CMD ["python", "-m", "worker_backend.entrypoint"]
