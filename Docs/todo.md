# Engineering Execution Backlog

This document tracks the execution backlog for the multi-cloud agentic document platform.
It follows a dual processing model: Track A (Admin/Template Ingest) and Track B (Candidate Processing), built on top of shared core foundations.

---

## Completed Tasks ✅
- [x] Epic 1, Story 1.1: Define canonical schema models (`TemplateAsset`, `TemplateRule`, `CandidateResume`, `ProcessingJob`, `ValidationResult`)
- [x] Epic 1, Story 1.2: Define domain interfaces (`DocumentExtractor`, `TemplateRepository`, etc.)
- [x] Epic 1, Story 1.3: Create common status, error, and event models (`JobStatus`, `AssetStatus`, etc.)
- [x] Epic 1, Story 1.4: Set up project module boundaries (incrementally aligned `backend/app/` structure)
- [x] Epic 1, Story 1.5: Implement common persistence abstractions (Added `StorageProvider` interface, `LocalStorageProvider`, and `S3StorageProvider` stub). Config updated to allow local/cloud switching.

---

## Remaining Backlog 📋

### Epic 1 — Core Contracts and Platform Foundation (Remaining)

#### Story 1.5a — Finish persistence/repository abstractions
- **Points:** 3
- **Tasks:**
  - Create remaining base repository abstractions (e.g. `BaseMetadataRepository`, `BaseJobRepository`).
  - Create transaction/unit-of-work boundary wrappers if necessary.
- **Acceptance Criteria:**
  - Repositories can be mocked in tests.
  - Basic read/write definitions exist for DB layers.

---

### Epic 2 — Admin Template Ingest and Governance
*Goal: implement admin-controlled onboarding, extraction, validation, indexing, approval, and publishing of templates and KB assets.*

#### Story 2.1 — Build admin asset upload API
- **Points:** 5
- **Tasks:**
  - Add admin upload endpoint and metadata submission endpoint.
  - Add request/response DTOs.
  - Add file validation and RBAC for admin users.
- **Acceptance Criteria:**
  - Admin can upload asset successfully; invalid types rejected.
  - API returns asset ID and draft status.

#### Story 2.2 — Implement template asset persistence
- **Points:** 3
- **Tasks:**
  - Store uploaded asset using `StorageProvider`.
  - Compute checksum and save draft metadata record.
  - Emit asset uploaded event.
- **Acceptance Criteria:**
  - Uploaded file is persisted.
  - Metadata record is created with draft status.
  - Upload event is audited.

#### Story 2.3 — Implement asset classification service
- **Points:** 5
- **Tasks:**
  - Support manual override of asset types (template, KB document, policy doc, etc.).
  - Implement auto-classification fallback.
- **Acceptance Criteria:**
  - Asset type/confidence saved. Manual type overrides auto-detection.

#### Story 2.4 — Implement template extraction service
- **Points:** 8
- **Tasks:**
  - Invoke `DocumentExtractor` adapter for admin asset.
  - Extract text and structure; persist extraction artifact.
  - Preserve provenance metadata.
- **Acceptance Criteria:**
  - Extraction artifact generated/stored. Provenance links back to original asset.

#### Story 2.5 — Implement template metadata service
- **Points:** 5
- **Tasks:**
  - Normalize fields (industry, role family, region, language, version, status).
  - Update metadata via API.
- **Acceptance Criteria:**
  - Metadata is stored normalized. Required fields enforced.

#### Story 2.6 — Implement template rule management
- **Points:** 8
- **Tasks:**
  - Create rule repository. Support manual attachment and parsed/imported rules.
  - Validate rule conflicts.
- **Acceptance Criteria:**
  - Rules can be retrieved by template ID/version. Conflicts flagged.

#### Story 2.7 — Implement KB chunking and indexing
- **Points:** 8
- **Tasks:**
  - Chunk knowledge assets and attach provenance.
  - Generate embeddings and write to search/vector index.
- **Acceptance Criteria:**
  - Approved KB assets chunked/indexed. Source/version provenance tracked.

#### Story 2.8 — Implement template validation service
- **Points:** 5
- **Tasks:**
  - Validate metadata, render config, rule refs, version conflicts.
  - Generate validation report.
- **Acceptance Criteria:**
  - Validation report shows pass/warn/fail. Asset blocked if critical validation fails.

#### Story 2.9 — Implement approval workflow
- **Points:** 5
- **Tasks:**
  - Submit asset for review, approve, reject.
  - Write audit trail for lifecycle transitions.
- **Acceptance Criteria:**
  - Only reviewer role can approve/reject. Audited state changes.

#### Story 2.10 — Implement publish workflow and template registry
- **Points:** 8
- **Tasks:**
  - Publish approved asset (mark active version, expose runtime lookup).
  - Implement rollback.
- **Acceptance Criteria:**
  - Runtime fetch uses active version. Rollback switches version correctly.

#### Story 2.11 — Build admin query/read APIs
- **Points:** 3
- **Tasks:**
  - List assets, filter by status/type, get asset by ID/version.
- **Acceptance Criteria:**
  - Admin can query/filter assets correctly.

---

### Epic 3 — Candidate Runtime Processing
*Goal: process candidate resumes/CVs through extraction, normalization, PII control, template selection, transformation, and output generation.*

#### Story 3.1 — Build candidate upload API
- **Points:** 5
- **Tasks:**
  - Runtime upload endpoint + job creation endpoint.
  - Add request DTOs and validate file/hints.
- **Acceptance Criteria:**
  - User can upload resume. API returns job ID + initial status.

#### Story 3.2 — Implement candidate upload and job initialization
- **Points:** 3
- **Tasks:**
  - Store raw file via `StorageProvider`.
  - Create processing job record and emit created event.
- **Acceptance Criteria:**
  - Raw file stored. Job starts at pending.

#### Story 3.3 — Implement candidate extraction service
- **Points:** 8
- **Tasks:**
  - Route to extractor adapter based on file type.
  - Persist raw extraction artifact.
- **Acceptance Criteria:**
  - Extraction artifact stored per job. Confidence captured.

#### Story 3.4 — Implement resume normalization service
- **Points:** 8
- **Tasks:**
  - Map extracted content to canonical schema. Detect standard sections.
  - Preserve source provenance.
- **Acceptance Criteria:**
  - Section mapping traceable back to source.

#### Story 3.5 — Implement PII policy engine
- **Points:** 8
- **Tasks:**
  - Tag identifiers and apply actions (retain/mask/redact/tokenize).
  - Build model-safe and recruiter-safe views.
- **Acceptance Criteria:**
  - Model input view excludes PII. Recruiter-safe output respects policy. Auditable log.

#### Story 3.6 — Implement template selection service
- **Points:** 8
- **Tasks:**
  - Query registry, filter/score candidate templates.
  - Support manual override.
- **Acceptance Criteria:**
  - Runtime selects template from published assets only. Rationale persisted.

#### Story 3.7 — Implement retrieval context builder
- **Points:** 5
- **Tasks:**
  - Fetch approved KB/rules/examples. Build compact retrieval bundle.
- **Acceptance Criteria:**
  - Bundle uses approved assets and includes provenance.

#### Story 3.8 — Implement summary generation service
- **Points:** 5
- **Tasks:**
  - Generate grounded recruiter summary using model-safe candidate view.
- **Acceptance Criteria:**
  - Summary artifact retrievable by job ID.

#### Story 3.9 — Implement transformation service
- **Points:** 8
- **Tasks:**
  - Map normalized resume into template structure. Create render payload.
  - Block unsupported additions (hallucinations).
- **Acceptance Criteria:**
  - Render payload aligns with template. Unsupported fields omitted.

---

### Epic 4 — Rendering and Output Validation

#### Story 4.1 — Implement validation engine
- **Points:** 8
- **Tasks:** Validate mandatory sections, chronology, template conformance, PII leakage.
- **Acceptance Criteria:** Pass/warn/fail checks persisted. Publishability determined.

#### Story 4.2 — Implement rendering service
- **Points:** 8
- **Tasks:** Render DOCX (and optionally PDF) using transformed content and published template package.
- **Acceptance Criteria:** Output refs stored in job metadata.

#### Story 4.3 — Implement runtime output/read APIs
- **Points:** 3
- **Tasks:** Endpoints to fetch job status, summary, validation report, artifacts.
- **Acceptance Criteria:** Missing outputs handled gracefully, access control enforced.

#### Story 4.4 — Implement feedback service
- **Points:** 3
- **Tasks:** Capture feedback (e.g. wrong template, extraction issue, PII issue) and emit analytics event.
- **Acceptance Criteria:** Feedback linked to job ID.

---

### Epic 5 — Workflow Orchestration

#### Story 5.1 — Implement admin asset ingest workflow
- **Points:** 5
- **Tasks:** Orchestrate upload → classify → extract → enrich → validate.
- **Acceptance Criteria:** Workflow updates status at each stage; handles retries.

#### Story 5.2 — Implement template approval/publish workflows
- **Points:** 5
- **Tasks:** Orchestrate review/approve/reject/publish/rollback.
- **Acceptance Criteria:** Publish blocked before approval.

#### Story 5.3 — Implement candidate processing workflow
- **Points:** 8
- **Tasks:** Orchestrate extract → normalize → PII → template select → retrieval → summary → transform → validate → render.
- **Acceptance Criteria:** End-to-end processing produces final state. Stage failures visible.

---

### Epic 6 — Adapters and Cloud Integrations

#### Story 6.1 — Implement extractor adapters
- **Points:** 8
- **Tasks:** Azure Document Intelligence adapter, local parser adapter.

#### Story 6.2 — Implement LLM provider adapter
- **Points:** 5
- **Tasks:** Azure OpenAI/Foundry adapter with policy wrapper.

#### Story 6.3 — Implement storage and search adapters
- **Points:** 5
- **Tasks:** DB adapter for metadata, vector index adapter for search.

---

### Epic 7 — Security, Auditability, and Observability

#### Story 7.1 — Implement RBAC and route authorization
- **Points:** 5
- **Tasks:** Enforce admin, reviewer, publisher, recruiter/user roles via API.

#### Story 7.2 — Implement audit logging
- **Points:** 5
- **Tasks:** Log asset/job lifecycles, PII actions, publish decisions.

#### Story 7.3 — Implement structured logs, metrics, and tracing
- **Points:** 5
- **Tasks:** Add job correlation IDs, latency metrics, stage failure counters.

---

### Epic 8 — Testing and Quality Hardening
- **Stories 8.1 - 8.4:** Unit tests for schemas/validators, service tests for admin/runtime lanes, and end-to-end workflow/adapter contract tests.
