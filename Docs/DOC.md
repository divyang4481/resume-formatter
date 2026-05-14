# Architecture Code Analysis (LangGraph, State, Patterns, Docling)

This document provides a code-level analysis of how architecture is implemented in the current repository, with special focus on:

- LangGraph workflow design and state handling
- Architectural patterns in use (ports/adapters, orchestration, fallback, policy boundaries)
- How Docling parsing is integrated and routed
- Gaps and refactor opportunities

---

## 1) Current Architecture at a Glance

The backend follows a layered approach with a clear **domain interface boundary** and pluggable adapters:

- **Domain interfaces / protocols** define contracts (`DocumentExtractionService`, `DocumentParser`, `StorageProvider`, etc.).
- **Service layer** orchestrates domain-level behavior (`ResumeIngestionService`, `ParserRouter`, template resolution/validation services).
- **Adapter layer** encapsulates implementation details (Docling, Azure Document Intelligence, cloud storage providers).
- **LangGraph workflow** composes request execution as a bounded, stage-based graph from ingest → parse → normalize → privacy → template resolution → transform → validate → render.

The design intent is strong: keep cloud/parser/provider specifics out of business workflow code.

---

## 2) LangGraph Workflow Analysis

### 2.1 Graph topology and execution order

In `backend/app/agent/graph.py`, `build_workflow_graph(...)` defines a linear graph:

1. `ingest`
2. `parse`
3. `normalize`
4. `privacy_transform`
5. `template_resolution`
6. `transform`
7. `validate`
8. `render`
9. `END`

```mermaid
flowchart LR
    A[ingest] --> B[parse]
    B --> C[normalize]
    C --> D[privacy_transform]
    D --> E[template_resolution]
    E --> F[transform]
    F --> G[validate]
    G --> H[render]
    H --> I((END))
```

Observations:

- The graph is currently **bounded and deterministic** (no dynamic branching/conditional edges yet).
- `template_resolution` and `transform` are the explicit "agentic" nodes using LLM runtime injection.
- Parse node depends on `DocumentExtractionService` and storage provider, reinforcing dependency inversion.

### 2.2 State contract quality

`backend/app/agent/state.py` uses a `TypedDict` (`AgentState`) as the graph state schema.

Strengths:

- Fields cover extraction output, normalized model, privacy model, template selection, validation, outputs, and orchestration flags.
- Intent metadata (`intent`, `actor_role`, `filename`, `content_type`) supports multi-lane behavior.

Risks / improvement points:

- `TypedDict` gives static shape but **no runtime validation** by default during graph transitions.
- Some fields are loosely typed (e.g., `formatting_rules: Optional[str]`, JSON payloads as strings).
- Node outputs are partially status-only (`{"status": "normalized"}`), so canonical payload propagation is still shallow in this implementation.

### 2.2.1 Workflow + state transition map

The graph advances by merging each node output dictionary into shared `AgentState`.

```mermaid
flowchart TD
    S0[Initial AgentState<br/>session_id, file_path, intent, actor_role] --> N1[ingest]
    N1 -->|status=ingested| S1[State + status]
    S1 --> N2[parse]
    N2 -->|extracted_text, extraction_confidence, status| S2[State + extraction fields]
    S2 --> N3[normalize]
    N3 -->|status=normalized| S3[State + normalization status]
    S3 --> N4[privacy_transform]
    N4 -->|status=privacy_applied| S4[State + privacy status]
    S4 --> N5[template_resolution]
    N5 -->|selected_template_id, status| S5[State + selected template]
    S5 --> N6[transform]
    N6 -->|transformed_document_json, validation flags, status| S6[State + transformed payload]
    S6 --> N7[validate]
    N7 -->|status=validated| S7[State + validation status]
    S7 --> N8[render]
    N8 -->|summary_uri, render_docx_uri, final status| S8[Final State]
```

### 2.3 Node implementation pattern

Node factories (`create_transform_node`, `create_template_resolve_node`, `create_render_node`) follow a closure-based dependency injection pattern:

- Inject runtime adapters once.
- Return node function that reads/writes `AgentState` fragments.

This is a good pattern for testability and replacement of implementations.

However:

- There is mixed sync/async handling in template resolution (`asyncio.run(...)` inside a sync node), which can cause event-loop issues in some runtimes.
- Graph-level retry, conditional routing, and checkpointer integration are not yet wired.

---

## 3) Architectural Patterns in Use

### 3.1 Ports & Adapters (Hexagonal) — actively used

The code consistently uses domain contracts with provider-specific adapters behind them.

Examples:

- `DocumentExtractionService` protocol (`backend/app/domain/interfaces/document_extraction.py`).
- `RouterBasedExtractionService` adapter bridging parser routing into the extraction service contract (`backend/app/services/extraction_service_adapter.py`).
- Storage and LLM provider selection through dependency factories (`backend/app/dependencies.py`).

### 3.2 Strategy + Fallback routing — parser path

`ParserRouter` is effectively a strategy selector with confidence-based fallback:

- Primary/fallback parser selected by extension and config.
- Primary parse attempt scored via `ParseConfidenceService`.
- Fallback executed when primary fails or confidence is below threshold.
- Rich trace emitted (`ParseResultTrace`, per-attempt telemetry).

This is a solid operational pattern for OCR/parser variability.

### 3.3 Pipeline orchestration

LangGraph wraps the end-to-end flow as stages, while services/adapters implement stage internals.

- Good separation: workflow orchestrates; adapters/services do work.
- Remaining gap: several stages are currently placeholders (normalize/privacy/validate) returning status only.

---

## 4) Docling Integration — Detailed Analysis

`backend/app/adapters/parsers/docling_parser.py`

### What it does now

- Lazily initializes `DocumentConverter`.
- Writes incoming bytes to a temporary file (cross-platform safety).
- Runs `converter.convert(tmp_path)`.
- Iterates document items to collect:
  - text/paragraph chunks
  - section headers mapped to `ParsedSection`
  - simple table extraction mapped to `ParsedTable`
- Exports full text as markdown via `doc.export_to_markdown()`.
- Returns `ParsedDocument` with `parser_used="docling"` and raw payload metadata.

```mermaid
sequenceDiagram
    participant Graph as LangGraph parse node
    participant RIS as ResumeIngestionService
    participant RES as RouterBasedExtractionService
    participant PR as ParserRouter
    participant DP as DoclingParser
    participant FS as Temp file system

    Graph->>RIS: ingest(file_bytes, filename, content_type, context)
    RIS->>RES: extract(...)
    RES->>PR: route_and_parse(...)
    PR->>DP: parse(...) (primary for configured types)
    DP->>FS: write bytes to temp file
    DP->>DP: DocumentConverter.convert(temp_path)
    DP->>DP: iterate_items() -> sections/tables/text
    DP->>DP: export_to_markdown()
    DP-->>PR: ParsedDocument(parser_used=docling)
    PR-->>RES: parsed_doc + parse trace
    RES-->>RIS: ExtractedDocument
    RIS-->>Graph: extracted_text + backend_used
```

### Strengths

- Produces richer structure than plain text parsers (sections/tables/markdown).
- Cleans up temp file in `finally` block.
- Declares capabilities (`tables`, `sections`, `markdown`, `ocr`).

### Constraints / caveats

- Converter initialization is in-process; heavy workloads may need worker pools.
- Parsing is CPU-bound and currently not offloaded to executor.
- Structured extraction is minimal (section content assembly and rich table semantics are basic).

---

## 5) Docling Parser Service Integration — Detailed Analysis

`backend/parser_service` now owns the heavy Docling runtime and exposes a lightweight HTTP contract to the worker.

### What it does now

- Accepts parse requests through `POST /parse-document`.
- Reads the source document from configured object storage.
- Runs Docling in the parser container.
- Writes normalized `ParsedDocument` JSON to object storage.
- Returns only lightweight metadata to the caller.

### Strengths

- Keeps Docling, Torch, and OCR dependencies out of the default worker image.
- Allows independent scaling for the parser container.
- Preserves the existing normalized parser output contract for downstream workflows.

### Constraints / caveats

- Parser-service availability is now required when `DOCUMENT_PARSER_PROVIDER=docling_service`.
- Parsing remains CPU-bound inside the parser container unless additional worker-pool or GPU scheduling is introduced.

---

## 6) Parser Routing Behavior

The effective behavior is defined by `ParserRouter` and `DOCUMENT_PARSER_PROVIDER`.

1. The worker receives a document processing job.
2. The configured parser provider is selected.
3. With `docling_service`, the worker writes input bytes to object storage and calls the parser service.
4. The parser service writes normalized parsed JSON back to object storage.
5. The worker loads the parsed JSON and continues the workflow.

```mermaid
flowchart TD
    A[Incoming file + metadata] --> B[ParserRouter]
    B --> C{DOCUMENT_PARSER_PROVIDER}
    C -->|docling_service| D[Call parser service]
    C -->|local_docling| E[Run Docling locally]
    D --> F[Parser writes ParsedDocument JSON]
    E --> G[Return ParsedDocument]
    F --> H[Worker loads parsed artifact]
    G --> H
    H --> I[Continue agent workflow]
```

Practical consequence:

- Docling is the supported local/heavy document parser.
- The default worker stays lightweight by routing heavy parsing to `parser-docling`.
- Additional cloud parser providers should use the same adapter boundary rather than embedding heavy runtimes in the worker.

---

## 7) State + Pattern Fit with Platform Goals

The architecture aligns with intended goals (bounded autonomy, governance, cloud agnostic), but implementation maturity is mixed:

- **Strong:** contract boundaries, adapter injection, parser routing with telemetry.
- **Partial:** state richness exists but many nodes are still placeholder outputs.
- **Needs hardening:** async model consistency, checkpointer adoption, and stronger runtime state validation.

---

## 8) Recommended Next Refactors (Priority Ordered)

1. **Unify async model in LangGraph nodes**
   - Convert synchronous nodes that call async code into native async nodes.
   - Remove nested `asyncio.run(...)` usage from node internals.

2. **Promote state schema from loose TypedDict to validated models at boundaries**
   - Keep `TypedDict` for graph compatibility if needed, but validate node I/O with Pydantic models.

3. **Complete currently stubbed stages**
   - `normalize`, `privacy_transform`, `validate` should write domain payloads (not only statuses).

4. **Persist and expose parse trace end-to-end**
   - Include parser attempts/confidence in job record and admin review UI.

5. **Deepen Docling structured mapping**
   - Build hierarchical sections and better table normalization.

6. **Add parser policy matrix by intent**
   - Candidate runtime vs admin asset ingest can have different parser preferences and confidence gates.

7. **Wire checkpointer for recoverability/audit**
   - Integrate graph checkpointing in compile/run path.

---

## 9) Documentation Consolidation Note

Architecture-focused documents have been moved to the root `Docs/` folder for a single documentation entry point:

- `Docs/ARCHITECTURE.md`
- `Docs/CLOUD_SERVICES.md`
- `Docs/ARCHITECTURE_CODE_ANALYSIS.md` (this file)
