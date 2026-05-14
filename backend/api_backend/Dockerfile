# API backend image: REST API + A2A discovery + MCP tool surface.
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

# Install only the shared library and API project dependencies. Heavy worker-only
# packages such as docling, torch, and sentence-transformers are intentionally
# absent from this image.
COPY ./common ./common
COPY ./api_backend ./api_backend
COPY ./app/api ./app/api
COPY ./app/adapters/repositories ./app/adapters/repositories
COPY ./app/adapters/queue ./app/adapters/queue
COPY ./app/adapters/storage ./app/adapters/storage
COPY ./app/adapters/knowledge_base_adapter.py ./app/adapters/knowledge_base_adapter.py
COPY ./app/db ./app/db
COPY ./app/domain ./app/domain
COPY ./app/schemas ./app/schemas
COPY ./app/services/hybrid_template_ranker.py ./app/services/hybrid_template_ranker.py
COPY ./app/services/template_lookup_service.py ./app/services/template_lookup_service.py
COPY ./app/services/template_publish_guard.py ./app/services/template_publish_guard.py
COPY ./app/services/template_service.py ./app/services/template_service.py
COPY ./app/utils ./app/utils
COPY ./app/config.py ./app/config.py
COPY ./app/dependencies.py ./app/dependencies.py
COPY ./app/main.py ./app/main.py
RUN pip install --no-cache-dir -e ./common -e ./api_backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()" || exit 1

CMD ["uvicorn", "api_backend.entrypoint:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
