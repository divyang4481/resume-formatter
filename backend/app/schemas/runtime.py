from pydantic import BaseModel, Field
from typing import Optional
from app.schemas.enums import JobStatus

class RuntimeDocumentSubmitResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str

class RuntimeJobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    original_file_ref: str
