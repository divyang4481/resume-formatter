from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.enums import PIIActionType


class PIIField(BaseModel):
    field_name: str
    original_value: str
    action_type: PIIActionType
    replacement_value: Optional[str] = None
    confidence_score: float = 1.0
    rationale: Optional[str] = None


class NormalizedSection(BaseModel):
    section_name: str
    raw_content: str
    normalized_content: Any = None
    confidence_score: float = 1.0
    source_provenance: Optional[str] = None


class CandidateResume(BaseModel):
    id: str
    job_id: str
    original_file_ref: str

    # Internal Structured Format
    personal_info: Dict[str, Any] = Field(default_factory=dict)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    sections: List[NormalizedSection] = Field(default_factory=list)

    # Policy tracking
    pii_actions: List[PIIField] = Field(default_factory=list)

    # Validation / Output specific properties
    is_model_safe: bool = False
    is_recruiter_safe: bool = False
    language: str = "en"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    extension_metadata: Dict[str, Any] = Field(default_factory=dict)
