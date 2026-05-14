from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class PlaceholderCandidate(BaseModel):
    marker: str
    candidate_kind: str  # e.g., "merge_marker", "repeat_start", "generic_fill_instruction"
    location: str
    context_snippet: Optional[str] = None


class SectionCandidate(BaseModel):
    heading: str
    level: int
    content_snippet: Optional[str] = None


class TableCandidate(BaseModel):
    label: str
    marker: str
    is_blank: bool
    row_index: int


class TemplateEvidence(BaseModel):
    placeholder_candidates: List[PlaceholderCandidate] = []
    section_candidates: List[SectionCandidate] = []
    tables: List[TableCandidate] = []
    instruction_blocks: List[str] = []
    object_patterns: Dict[str, List[str]] = {}
    repeated_markers: List[str] = []
    bullet_slots: List[str] = []
    raw_text_summary: Optional[str] = None


class TemplateField(BaseModel):
    fieldname: str
    canonical_fieldname: Optional[str] = None
    original_label: Optional[str] = None
    marker_text: str
    field_type: str
    meaning: str
    source_hints: Optional[Union[str, List[str]]] = None
    resume_fillable: bool = True
    language: str = "en"
    semantic_inference: Optional[str] = None
    confidence: float = 0.0
    sub_fields: List["TemplateField"] = []


TemplateField.model_rebuild()


class TemplateManifest(BaseModel):
    template_id: str
    purpose: str
    fields: List[TemplateField] = []
    language: str = "en"
    analysis_status: str = "pending"  # pending, completed, partial, failed
    validation_errors: List[str] = []
    validation_warnings: List[str] = []
    requires_human_review: bool = False
    review_reasons: List[str] = []
    average_confidence: Optional[float] = None
    model_usage: Dict[str, Any] = Field(default_factory=dict)
    complexity_score: Optional[float] = None
    llm_attempt_count: int = 1
    repair_attempt_count: int = 0
