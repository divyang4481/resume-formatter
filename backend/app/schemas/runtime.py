from pydantic import BaseModel, Field
from typing import Optional
from app.schemas.enums import JobStatus

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

class RuntimeJobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    original_file_ref: str
