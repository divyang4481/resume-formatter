# Worker backend image: consumes queue messages and executes document workflows.
# Build context must be the backend/ directory.
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=1000 \
    POETRY_REQUESTS_TIMEOUT=1000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gcc \
    g++ \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --all-extras \
    && pip install --no-cache-dir rapidocr-onnxruntime

# Copy the shared application package and this backend's entrypoint.
COPY ./app ./app
COPY ./worker_backend ./worker_backend
COPY ./init_db.py ./init_db.py

RUN mkdir -p .data \
    && python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"

CMD ["python", "-m", "worker_backend.entrypoint"]
