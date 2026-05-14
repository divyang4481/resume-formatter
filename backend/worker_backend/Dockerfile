# Worker backend image: consumes queue messages and executes document workflows.
# Build context must be the backend/ directory.
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=1000

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

# Install the shared library and worker project dependencies. The worker owns
# heavy extraction/runtime dependencies such as docling, torch, and RapidOCR.
COPY ./common ./common
COPY ./worker_backend ./worker_backend
COPY ./app ./app
COPY ./init_db.py ./init_db.py
RUN pip install --no-cache-dir -e ./common -e ./worker_backend \
    && pip install --no-cache-dir rapidocr-onnxruntime

RUN mkdir -p .data \
    && python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"

CMD ["python", "-m", "worker_backend.entrypoint"]
