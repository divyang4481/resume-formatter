# Agentic Document Platform

A **Template-aware, privacy-governed, agentic document processing platform** designed to transform unstructured documents such as resumes, CVs, and consultant profiles into structured, template-driven outputs.

## Overview
This platform is built as a **workflow-centric, cloud-agnostic system**. It avoids free-roaming autonomous agents in favor of **bounded agentic workflows** (powered by LangGraph) where reasoning is used safely for extraction cleanup, template mapping, summarization, and privacy-aware PII handling.

## Key Features
- **Workflow First**: Predictable orchestration pipelines.
- **Cloud-Agnostic Core**: Core business logic remains portable. Cloud-specific services (AWS Textract, Azure Document Intelligence, GCP Document AI) are isolated behind adapters.
- **Privacy by Policy**: PII handled through strict, deterministic rules, not ad-hoc LLM masking.
- **Template Intelligence**: Templates are governed assets dictating schemas and deterministic rendering.
- **A2A and MCP Support**: Built-in discoverability for agent-to-agent communication and Model Context Protocol integrations for cloud native tool calling.

## Installation and Setup

### 1. Requirements
- Python 3.11+
- [Poetry](https://python-poetry.org/) 2.0+

### 2. Dependency Management
This project uses Poetry with dependency groups to keep the deployment weight light and cloud-specific.

Install the core dependencies:
```bash
poetry install
```

Install cloud-specific adapters (e.g., for AWS, Azure, GCP, IBM, or Local Tika fallback):
```bash
poetry install --extras "aws"
poetry install --extras "azure"
poetry install --extras "gcp"
poetry install --extras "ibm"
poetry install --extras "local"
```

### 3. Running Locally
Run the platform natively using Uvicorn:
```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or via Docker Compose:
```bash
cd docker
docker-compose up --build
```

### 4. Configuration
See the `config/` directory. By default, the app runs as `local`. Modify `.env` or set environment variables such as `CLOUD` and `DOCUMENT_PARSER_BACKEND` to target AWS, Azure, or GCP specific adapter implementations.
