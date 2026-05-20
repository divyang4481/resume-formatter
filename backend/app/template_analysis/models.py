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
    placeholder_candidates: List[PlaceholderCandidate] = Field(default_factory=list)
    section_candidates: List[SectionCandidate] = Field(default_factory=list)
    tables: List[TableCandidate] = Field(default_factory=list)
    instruction_blocks: List[str] = Field(default_factory=list)
    object_patterns: Dict[str, List[str]] = Field(default_factory=dict)
    repeated_markers: List[str] = Field(default_factory=list)
    bullet_slots: List[str] = Field(default_factory=list)
    paste_zones: List[str] = Field(default_factory=list)
    header_footer_markers: List[str] = Field(default_factory=list)
    table_loops: List[Dict[str, Any]] = Field(default_factory=list)
    table_loop_fields: Dict[str, List[str]] = Field(default_factory=dict)
    heading_to_loop: Dict[str, str] = Field(default_factory=dict)
    blank_label_slots: List[str] = Field(default_factory=list)
    layout_style: str = "freeflow"
    raw_structure: Dict[str, Any] = Field(default_factory=dict)
    raw_text_summary: Optional[str] = None
    docling_markdown: Optional[str] = None


class TemplateField(BaseModel):
    fieldname: str
    canonical_fieldname: Optional[str] = None
    original_label: Optional[str] = None
    marker_text: str
    field_type: str
    meaning: str
    source_hints: Optional[Union[str, List[str]]] = None
    resume_fillable: bool = True
    source_kind: str = "resume_fact"
    required: bool = False
    language: str = "en"
    semantic_inference: Optional[str] = None
    confidence: float = 0.0
    occurrence_index: int = 1
    context: Dict[str, Any] = Field(default_factory=dict)
    extraction_hints: Dict[str, Any] = Field(default_factory=dict)
    injection_hints: Dict[str, Any] = Field(default_factory=dict)
    render_locator: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    sub_fields: List["TemplateField"] = Field(default_factory=list)


TemplateField.model_rebuild()


class TemplateManifest(BaseModel):
    template_id: str
    purpose: str
    fields: List[TemplateField] = Field(default_factory=list)
    field_count: int = 0
    evidence_summary: Dict[str, Any] = Field(default_factory=dict)
    extraction_contract: Dict[str, Any] = Field(default_factory=dict)
    injection_contract: Dict[str, Any] = Field(default_factory=dict)
    language: str = "en"
    analysis_status: str = "pending"  # pending, completed, partial, failed
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    requires_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
    average_confidence: Optional[float] = None
    model_usage: Dict[str, Any] = Field(default_factory=dict)
    complexity_score: Optional[float] = None
    llm_attempt_count: int = 1
    repair_attempt_count: int = 0
