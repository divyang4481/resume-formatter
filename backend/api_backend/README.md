# API Backend

This folder contains the container-specific API backend entrypoint and Dockerfile.
It is responsible for the externally reachable service surface:

- REST API endpoints under `/api/*`
- A2A discovery endpoints, including `/.well-known/agent-card.json`
- MCP tool exposure mounted by the FastAPI application
- OpenAPI documentation at `/docs` and `/openapi.json`

The API backend intentionally reuses the shared application package in
`backend/app/` so route handlers, schemas, services, repositories, adapters, and
workflow logic remain single-sourced.

## Local container build

From the repository root:

```bash
docker build -t agentic-doc-api-local -f backend/api_backend/Dockerfile backend
```

## Local process run

From `backend/`:

```bash
poetry run uvicorn api_backend.entrypoint:create_app --factory --host 0.0.0.0 --port 8000 --reload
```
