from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.schemas.enums import JobStatus, ExecutionMode

class ExecutionContext(BaseModel):
    mode: ExecutionMode = ExecutionMode.RECRUITER_RUNTIME
    actor_role: str = "recruiter"
    template_id: Optional[str] = None
    test_run_id: Optional[str] = None

class SubmitDocumentResponse(BaseModel):
    document_id: str
    job_id: str
    status: JobStatus
    requires_confirmation: bool
    provided_industry_id: Optional[str] = None
    provided_template_id: Optional[str] = None
    suggested_industry_id: Optional[str] = None
    suggested_template_id: Optional[str] = None
    allowed_template_ids: Optional[list[str]] = None
    message: Optional[str] = None

class ConfirmDocumentRequest(BaseModel):
    industry_id: str
    template_id: str

from typing import Any, Dict, List, Optional

class RuntimeJobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    original_file_ref: str
    stage: Optional[str] = None
    error_message: Optional[str] = None
    suggested_template_ids: Optional[List[str]] = None
    suggested_template_scores: Optional[List[Dict[str, Any]]] = None
    document_kind: Optional[str] = None
    document_confidence: Optional[float] = None
    document_reason: Optional[str] = None
    
    # Audit & Validation Fields
    validation_passed: Optional[bool] = None
    validation_report: Optional[str] = None
    
    # Generated Outputs
    summary: Optional[str] = None

