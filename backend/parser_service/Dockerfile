# Dedicated parser image: owns Docling/Torch/OCR so api and worker images stay lite.
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

COPY ./common ./common
COPY ./parser_service ./parser_service
COPY ./app/adapters/aws_client.py ./app/adapters/aws_client.py
COPY ./app/adapters/parsers ./app/adapters/parsers
COPY ./app/adapters/storage ./app/adapters/storage
COPY ./app/config.py ./app/config.py
COPY ./app/domain ./app/domain
COPY ./app/schemas ./app/schemas
RUN pip install --no-cache-dir -e ./common -e ./parser_service

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).read()" || exit 1

CMD ["uvicorn", "parser_service.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
