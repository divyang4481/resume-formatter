# Agentic Document Platform

A **Template-aware, privacy-governed, agentic document processing platform** designed to transform unstructured documents such as resumes, CVs, and consultant profiles into structured, template-driven outputs.

---

## Overview

This platform is built as a **workflow-centric, cloud-agnostic system**. It avoids free-roaming autonomous agents in favor of **bounded agentic workflows** (powered by LangGraph) where reasoning is used safely for extraction cleanup, template mapping, summarization, and privacy-aware PII handling.

---

## Key Features

- **Workflow First** — Predictable orchestration pipelines, not autonomous agents.
- **Cloud-Agnostic Core** — Core business logic remains portable. Cloud-specific services (AWS Textract, Azure Document Intelligence, GCP Document AI) are isolated behind adapters.
- **Privacy by Policy** — PII handled through strict, deterministic rules, not ad-hoc LLM masking.
- **Template Intelligence** — Templates are governed assets dictating schemas and deterministic rendering.
- **A2A and MCP Support** — Built-in discoverability for agent-to-agent communication and Model Context Protocol integrations for cloud-native tool calling.

---

## Environment Strategy

This project follows a **layered environment model** that separates system/runtime concerns from application dependency management.

### Environment Layer Overview

| Layer | Tool | Responsibility |
|---|---|---|
| OS / CUDA / Python runtime | **Conda** | System-level deps, GPU libs, Python version pinning |
| App dependencies (core) | **Poetry** | FastAPI, LangGraph, Pydantic — minimal and portable |
| Cloud adapters | **Poetry extras** | AWS, Azure, GCP, IBM SDKs — isolated per cloud target |
| Environment isolation | **Separate Poetry envs** | One env per cloud profile to prevent SDK conflicts |

> **Why not one big environment?**
> AWS, Azure, and GCP SDKs have overlapping transitive dependencies that frequently conflict at version boundaries. Separate Poetry environments per cloud profile mirror the adapter-based architecture and prevent cross-cloud pollution.

---

## Installation and Setup

### 1. Requirements

- Python **3.11+**
- [Poetry](https://python-poetry.org/) **2.0+**
- (Optional) [Conda](https://docs.conda.io/) — for GPU/ML workloads or system-level dependencies

---

### 2. Conda + Poetry Hybrid Setup (Recommended)

Use Conda **only** for the system/runtime layer (Python version, CUDA, native libs), then let Poetry manage all application dependencies inside that environment.

```bash
# Create and activate Conda env for the runtime layer
conda create -n adp-platform python=3.11
conda activate adp-platform

# Tell Poetry NOT to create its own venv (use the active Conda env)
poetry config virtualenvs.create false

# Install core application dependencies
poetry install
```

> **When to use this?**  
> Use the Conda+Poetry hybrid when you need GPU/ML libraries (torch, CUDA bindings) or other system-compiled packages that pip/Poetry cannot reliably install cross-platform.

---

### 3. Pure Poetry Setup (Standard — no GPU/ML)

For pure cloud/document processing workloads with no GPU requirements:

```bash
# Pin Python version for the environment
poetry env use python3.11

# Install core dependencies only
poetry install
```

---

### 4. Cloud-Specific Adapter Installs (Extras)

Each cloud adapter is an **isolated extra**. Install only the adapter matching your deployment target.

#### Core only (no cloud SDK)
```bash
poetry install
```

#### AWS
```bash
poetry install --extras "cloud-aws-native"
```

#### Azure
```bash
poetry install --extras "cloud-azure-native"
```

#### GCP
```bash
poetry install --extras "cloud-gcp-native"
```

#### Local runtime emulation (with LocalStack / Azurite)
```bash
poetry install --extras "runtime-local-aws"
poetry install --extras "runtime-local-azure"
poetry install --extras "runtime-local-gcp"
```

#### Parser engines (pluggable extraction backends)
```bash
poetry install --extras "parser-docling"    # Docling (default)
poetry install --extras "parser-tika"       # Apache Tika (fallback)
poetry install --extras "parser-unstructured"  # Unstructured.io
```

#### Dev/Test environment
```bash
poetry install --extras "dev-local"
```

> **Tip:** You can combine extras in a single install:
> ```bash
> poetry install --extras "cloud-aws-native parser-docling dev-local"
> ```

---

### 5. Per-Profile Environment Management (Multi-Cloud Dev)

For developers working across multiple cloud targets simultaneously, use separate named Poetry environments:

```bash
poetry env use python3.11

# List all managed environments
poetry env list

# Activate a specific env (example: shell into it)
poetry env info
```

Recommended naming convention when managing multiple envs externally:

```
adp-core
adp-aws
adp-azure
adp-gcp
```

This gives **true isolation**: AWS SDK conflicts do not infect the Azure environment and vice versa — matching the adapter isolation already enforced at the code level.

---

### 6. Running Locally

Run the platform natively using Uvicorn:

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or via Docker Compose:

```bash
cd docker
docker-compose up --build
```

---

### 7. Configuration

See the `config/` directory. By default, the app runs as `local`. Modify `.env` or set environment variables such as `CLOUD` and `DOCUMENT_PARSER_BACKEND` to target AWS, Azure, or GCP-specific adapter implementations.

Example `.env` values:

```env
CLOUD=aws
DOCUMENT_PARSER_BACKEND=textract
```

---

## CI/CD Matrix Strategy

The extras-based environment model enables a **parallel CI/CD matrix** that validates each cloud adapter independently:

| Pipeline | Extras Installed | Validates |
|---|---|---|
| `build-core` | _(none)_ | Core logic, routing, schemas |
| `build-aws` | `cloud-aws-native` | AWS Textract adapter |
| `build-azure` | `cloud-azure-native` | Azure Document Intelligence adapter |
| `build-gcp` | `cloud-gcp-native` | GCP Document AI adapter |
| `build-local` | `runtime-local-aws` | LocalStack emulation tests |

> This gives **true cloud-agnostic validation**: a broken AWS SDK version does not block an Azure or GCP deploy.

---

## Dependency Design (pyproject.toml)

The `pyproject.toml` follows this principle: **keep core minimal, push cloud concerns to extras**.

```toml
[project.dependencies]
# Only what every deployment needs
fastapi = "..."
pydantic = "..."
langgraph = "..."

[project.optional-dependencies]
cloud-aws-native    = ["boto3"]
cloud-azure-native  = ["azure-ai-documentintelligence", "azure-storage-blob", "azure-identity"]
cloud-gcp-native    = ["google-cloud-documentai", "google-cloud-storage"]
parser-docling      = ["docling"]
parser-tika         = ["tika"]
parser-unstructured = ["unstructured"]
dev-local           = ["pytest", "pytest-asyncio"]
```

---

## Project Structure

```
backend/
├── app/               # Core application (routes, workflows, adapters)
├── config/            # Environment and cloud configuration
├── docker/            # Docker Compose and Dockerfiles
├── docs/              # Architecture and design documentation
├── policies/          # PII and privacy policy rules
├── templates/         # Governed output template definitions
├── tests/             # Test suites (unit, integration)
├── pyproject.toml     # Dependency manifest with extras
└── README.md
```

---

## Design Philosophy

This platform enforces three non-negotiable principles:

1. **Cloud abstraction** — No cloud SDK leaks into core business logic.
2. **Adapter isolation** — Each cloud provider lives behind a single swappable interface.
3. **Workflow determinism** — Agentic reasoning is bounded; outputs are always schema-validated.

Your environments should reflect your architecture. That is why this project uses **Poetry extras + isolated envs** rather than a single monolithic environment.
