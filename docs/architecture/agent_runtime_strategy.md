# Agent Runtime Strategy: Container Boundary vs. Amazon Bedrock AgentCore

This note captures the current agent boundary in the application and the recommended path for splitting the agent code into an extractable subproject while keeping a pragmatic deployment strategy.

## Current code boundary

The backend already has a useful agent seam:

- `backend/app/domain/interfaces/agent.py` defines the provider-neutral `ResumeFormattingAgent` contract for mapping resumes, generating template contracts, and evaluating output quality.
- `backend/app/adapters/agent/python_agent.py` implements the same contract with in-process Python orchestration and the configured LLM runtime.
- `backend/app/adapters/agent/bedrock_agent.py` implements the same contract by invoking an AWS Bedrock Agent.
- `backend/app/dependencies.py` chooses the provider from `settings.agent_provider`, so runtime selection is configuration-driven rather than hard-coded.
- `backend/app/agent/graph.py` still owns the LangGraph-style workflow for template and resume processing, including template resolution, resume extraction, summary generation, manifest mapping, DOCX composition, and quality validation.

That means the code is already close to a subproject boundary: the application can depend on a small agent package that exposes the interface, provider implementations, graph builders, state models, prompts, and tests.

## Recommended extractable subproject shape

If we extract the agent from `backend/app/`, use a lightweight package first instead of creating a separate repository immediately:

```text
backend/agent_runtime/
  pyproject.toml
  agent_runtime/
    __init__.py
    interfaces.py
    state.py
    graph.py
    prompts/
    providers/
      python_orchestrated.py
      bedrock_agent.py
      agentcore_runtime.py   # future
      agentcore_memory.py    # future
    services/
      json_cleaning.py
      prompt_manager.py
  tests/
```

Keep these dependencies flowing inward:

1. `backend/api_backend` and `backend/worker_backend` can import `agent_runtime`.
2. `agent_runtime` should not import FastAPI routes, SQLAlchemy models, or concrete API/worker entrypoints.
3. Storage, parser, LLM, knowledge, and job-progress integrations should remain injected interfaces so the agent package is portable.
4. The existing `ResumeFormattingAgent` contract should stay stable while adding new optional capabilities through separate interfaces, for example `AgentMemoryStore`.

## Container vs. AgentCore recommendation

### Keep our current containers as the default runtime now

The current workflow is document-heavy and deterministic in several places: parsing, template selection, manifest validation, DOCX rendering, storage writes, job status updates, and queue consumption. Containers remain the best default because they:

- run the same code locally with Docker Desktop, in ECS/Fargate, or in Kubernetes;
- keep Docling/parser dependencies and DOCX rendering under our control;
- make LocalStack/Postgres integration testing straightforward;
- avoid forcing every pipeline step through an agent session abstraction;
- preserve existing observability around worker stages and job status transitions.

### Use Bedrock AgentCore selectively, not as a full replacement yet

As of the 2026-05-14 review, AWS positions Amazon Bedrock AgentCore Runtime as a managed, serverless runtime for deploying and scaling agents built with common frameworks/protocols, and AgentCore Memory as managed session/long-term memory with automated embedding/storage concerns. Relevant AWS references:

- Product overview: <https://aws.amazon.com/bedrock/agentcore/>
- FAQ: <https://aws.amazon.com/bedrock/agentcore/faqs/>
- Runtime quickstart: <https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/runtime/quickstart.html>
- Memory API reference: <https://aws.github.io/bedrock-agentcore-starter-toolkit/api-reference/memory.html>
- Service quotas: <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html>
- Pricing: <https://aws.amazon.com/bedrock/agentcore/pricing/>

AgentCore can add value if we use it for bounded agent responsibilities:

- resume-to-template reasoning where the prompt/tool loop benefits from managed sessions;
- cross-job learning such as recruiter preferences, template mapping corrections, and repeated company-specific formatting rules;
- tool exposure through Gateway/MCP where governance, identity, and centralized audit are more valuable than in-process calls;
- production scale where serverless agent isolation is preferable to scaling our worker containers for LLM orchestration.

Do not move parsing, S3/SQS/Postgres integration, DOCX rendering, or job orchestration into AgentCore first. Those are predictable application services and are easier to test and operate in the worker container.

## Memory guidance

AgentCore Memory is worth a proof-of-concept for durable preferences and learned corrections, but not for transient pipeline state. Use this split:

| State type | Recommended home | Why |
| --- | --- | --- |
| Job status, artifacts, audit trail | Postgres + object storage | Must be deterministic, queryable, and retained by product rules. |
| Queue handoff | SQS/LocalStack | Operational workflow state, not agent memory. |
| Per-job graph state | Worker process + persisted checkpoints if needed | Short-lived and tied to retry semantics. |
| User/team formatting preferences | AgentCore Memory candidate | Reusable across jobs and suitable for contextual recall. |
| Template correction history | AgentCore Memory or explicit DB table | Use AgentCore if fuzzy recall helps; use DB if exact governance/reporting is required. |
| PII policy and compliance rules | Versioned config/DB, not memory | Must be explicit and auditable, not emergent recall. |

## Proposed migration path

1. **Package boundary first:** move only interface/graph/provider/prompt code into an internal `agent_runtime` package while preserving the current `python_orchestrated` provider.
2. **Add memory interface:** introduce an `AgentMemoryStore` port with a local no-op or Postgres-backed implementation. Use it only for preferences/corrections, not compliance state.
3. **AgentCore adapter spike:** add an `agentcore_runtime` provider behind `AGENT_PROVIDER=agentcore_runtime` and keep the same input/output JSON contract.
4. **Shadow mode:** run AgentCore for selected jobs without affecting user output, compare field mapping quality, latency, cost, retries, and policy behavior.
5. **Promote selectively:** use AgentCore for mapping/quality reasoning only if shadow metrics beat or simplify the current container path.

## Decision

Use our containerized worker/API stack as the production baseline. Extract the agent code into a package boundary to make it portable. Evaluate AgentCore Runtime and Memory as optional adapters for reasoning and reusable preferences, not as replacements for the entire document-processing pipeline.
