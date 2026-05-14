# Worker Backend

This folder contains the container-specific worker backend entrypoint and
Dockerfile. It is responsible for background job execution:

- Polling the configured queue provider
- Loading documents from the configured storage provider
- Running resume/template processing workflows
- Persisting job state and output artifacts

The worker backend is a separate Python project that depends on
`backend/common/` for shared schemas, database models, repositories, queue, and
storage code. Unlike the API project, it owns the heavy document extraction and
agentic workflow dependencies such as Docling, Torch, LangGraph, and RapidOCR.

## Local container build

From the repository root:

```bash
docker build -t agentic-doc-worker-local -f backend/worker_backend/Dockerfile backend
```

## Local process run

From `backend/`:

```bash
pip install -e common -e worker_backend
python -m worker_backend.entrypoint
```
