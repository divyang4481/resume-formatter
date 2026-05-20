from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class TemplateAsset(Base):

    __tablename__ = "template_assets"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    role_family = Column(String, nullable=True)
    region = Column(String, nullable=True)
    language = Column(String, default="en")
    file_name = Column(String, nullable=True)

    notes = Column(Text, nullable=True)
    purpose = Column(Text, nullable=True)
    expected_sections = Column(Text, nullable=True)
    expected_fields = Column(Text, nullable=True) # Comma-separated list of identified placeholders
    # Logical Relationships:
    # - Master record for a resume template shell.
    # - Linked to 'processing_jobs' via template_asset_id.
    # - Defines the 'contract' (expected_fields/manifest) for data mapping.
    # - status can be DRAFT, ACTIVE, ARCHIVED.
    field_extraction_manifest = Column(Text, nullable=True) # Rich JSON mapping of fieldname, meaning, source_hints
    summary_guidance = Column(Text, nullable=True)
    docling_extraction = Column(Text, nullable=True)  # Raw Docling extraction output

    formatting_guidance = Column(Text, nullable=True)
    validation_guidance = Column(Text, nullable=True)
    pii_guidance = Column(Text, nullable=True)
    selection_weight = Column(Integer, default=50)
    is_default_for_industry = Column(Boolean, default=False)
    analysis_json = Column(Text, nullable=True) # Full TemplateAnalysis model
    requires_human_review = Column(Boolean, default=False)
    review_reasons = Column(Text, nullable=True) # JSON list of reasons
    model_usage_json = Column(Text, nullable=True)
    complexity_score = Column(Float, nullable=True)
    llm_attempt_count = Column(Integer, default=1)



    storage_uri = Column(String, nullable=True)
    extraction_uri = Column(String, nullable=True)
    checksum_sha256 = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TemplateRule(Base):
    __tablename__ = "template_rules"

    id = Column(String, primary_key=True, index=True)
    template_asset_id = Column(String, ForeignKey("template_assets.id"), nullable=False)
    rule_type = Column(String, nullable=False)
    rule_name = Column(String, nullable=False)
    rule_payload_json = Column(Text, nullable=False)
    severity = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class CandidateResume(Base):
    __tablename__ = "candidate_resumes"

    id = Column(String, primary_key=True, index=True)
    source_file_name = Column(String, nullable=False)
    source_storage_uri = Column(String, nullable=False)
    extraction_uri = Column(String, nullable=True)
    # Logical Relationships:
    # - Represents a single candidate's source resume data.
    # - Linked to 'processing_jobs' via candidate_resume_id.
    # - Stores the persistent "ground truth" facts extracted from the resume.
    normalized_resume_json = Column(Text, nullable=True)
    resume_summary = Column(Text, nullable=True)
    industry_hint = Column(String, nullable=True)
    template_hint = Column(String, nullable=True)
    candidate_facts_json = Column(Text, nullable=True) # Canonical CandidateFacts model
    created_at = Column(DateTime, default=datetime.utcnow)

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String, primary_key=True, index=True)
    candidate_resume_id = Column(String, ForeignKey("candidate_resumes.id"), nullable=True)
    job_type = Column(String, nullable=False, default="RESUME_FORMATTING")
    original_file_ref = Column(String, nullable=True)
    # Logical Relationships:
    # - The orchestration record that ties a CandidateResume to a TemplateAsset.
    # - If job_type=TEMPLATE_PROCESSING: original_file_ref is the template itself.
    # - If job_type=RESUME_FORMATTING: original_file_ref is the resume, and template_asset_id is the target template.
    # - Stores the output artifacts: generated_summary, summary_uri, render_docx_uri.
    template_asset_id = Column(String, ForeignKey("template_assets.id"), nullable=True)
    template_version = Column(String, nullable=True)
    status = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    summary_uri = Column(String, nullable=True)
    generated_summary = Column(Text, nullable=True)
    render_docx_uri = Column(String, nullable=True)
    transformed_json = Column(Text, nullable=True)
    candidate_facts_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Improved Audit Metadata for Template Analysis / LLM stages
    model_usage_json = Column(Text, nullable=True) # Audit log of models used
    complexity_score = Column(Float, nullable=True)
    llm_attempt_count = Column(Integer, default=1)
    repair_attempt_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(String, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("processing_jobs.id"), nullable=False)
    validation_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    passed = Column(Boolean, nullable=False)
    message = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class KnowledgeAsset(Base):
    __tablename__ = "knowledge_assets"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False)
    pack_id = Column(String, ForeignKey("knowledge_packs.id"), nullable=True)
    asset_kind = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    role_family = Column(String, nullable=True)
    region = Column(String, nullable=True)
    language = Column(String, default="en")
    file_name = Column(String, nullable=True)
    storage_uri = Column(String, nullable=True)
    extraction_uri = Column(String, nullable=True)
    checksum_sha256 = Column(String, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class KnowledgePack(Base):
    __tablename__ = "knowledge_packs"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    pack_type = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    role_family = Column(String, nullable=True)
    region = Column(String, nullable=True)
    language = Column(String, default="en")
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class TemplateKnowledgeBinding(Base):
    __tablename__ = "template_knowledge_bindings"

    id = Column(String, primary_key=True, index=True)
    template_asset_id = Column(String, ForeignKey("template_assets.id"), nullable=False)
    template_version = Column(String, nullable=False)
    knowledge_pack_id = Column(String, ForeignKey("knowledge_packs.id"), nullable=False)
    binding_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class LocalQueueMessage(Base):
    __tablename__ = "local_queue_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    queue_name = Column(String, index=True, nullable=False)
    payload_json = Column(Text, nullable=False)
    status = Column(String, default="pending", index=True) # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TemplateTestRun(Base):
    __tablename__ = "template_test_runs"

    id = Column(String, primary_key=True, index=True)
    template_id = Column(String, ForeignKey("template_assets.id"), nullable=False)
    sample_resume_asset_id = Column(String, nullable=True)
    processing_job_id = Column(String, nullable=False)
    decision = Column(String, nullable=True) # PASS, FAIL, None
    review_notes = Column(Text, nullable=True)
    generated_summary = Column(Text, nullable=True)
    output_doc_path = Column(String, nullable=True)
    output_pdf_path = Column(String, nullable=True)
    extracted_json_path = Column(String, nullable=True)
    validation_result_json = Column(Text, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
