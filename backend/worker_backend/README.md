# Worker Backend

This folder contains the container-specific worker backend entrypoint and
Dockerfile. It is responsible for background job execution:

- Polling the configured queue provider
- Loading documents from the configured storage provider
- Running resume/template processing workflows
- Persisting job state and output artifacts

The worker backend intentionally reuses the shared application package in
`backend/app/` so domain logic, adapters, schemas, repositories, and workflows
remain single-sourced.

## Local container build

From the repository root:

```bash
docker build -t agentic-doc-worker-local -f backend/worker_backend/Dockerfile backend
```

## Local process run

From `backend/`:

```bash
poetry run python -m worker_backend.entrypoint
```
