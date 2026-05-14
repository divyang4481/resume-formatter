# API Backend

This folder contains the container-specific API backend entrypoint and Dockerfile.
It is responsible for the externally reachable service surface:

- REST API endpoints under `/api/*`
- A2A discovery endpoints, including `/.well-known/agent-card.json`
- MCP tool exposure mounted by the FastAPI application at `/mcp`
- Capability and health checks at `/api/capabilities` and `/api/health`
- OpenAPI documentation at `/docs` and `/openapi.json`

The API backend is now a separate Python project that depends on
`backend/common/` for shared schemas, database models, repositories, queue, and
storage code. Its container copies only API-facing modules and intentionally
leaves worker-only extraction/runtime packages such as Docling and Torch out of
the image.

## Local container build

From the repository root:

```bash
docker build -t agentic-doc-api-local -f backend/api_backend/Dockerfile backend
```

## Local process run

From `backend/`:

```bash
pip install -e common -e api_backend
uvicorn api_backend.entrypoint:create_app --factory --host 0.0.0.0 --port 8000 --reload
```
