from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.enums import JobStatus, StageStatus, ValidationCheckStatus


class ValidationResult(BaseModel):
    id: str
    job_id: str
    status: ValidationCheckStatus
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    report_artifact_ref: Optional[str] = None
    confidence_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessingStageStatus(BaseModel):
    stage_name: str
    status: StageStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessingJob(BaseModel):
    id: str
    status: JobStatus = JobStatus.CREATED
    candidate_id: Optional[str] = None
    original_file_ref: str

    # Processed Artifact References
    extraction_artifact_ref: Optional[str] = None
    normalized_resume_ref: Optional[str] = None
    rendered_output_refs: List[str] = Field(default_factory=list)
    validation_result_id: Optional[str] = None

    # Generated Outputs
    summary_uri: Optional[str] = None
    render_docx_uri: Optional[str] = None

    # Extraction Quality
    extraction_quality_score: Optional[float] = None
    missing_fields: Optional[List[str]] = None

    # Template and Context selection
    selected_template_id: Optional[str] = None
    template_version: Optional[str] = None
    selection_rationale: Optional[str] = None

    # Workflow Stage Statuses
    stages: List[ProcessingStageStatus] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str

    extension_metadata: Dict[str, Any] = Field(default_factory=dict)
