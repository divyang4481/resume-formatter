from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.enums import AssetStatus


class TemplateRule(BaseModel):
    id: str
    template_id: str
    version: str
    rule_type: str = Field(..., description="E.g., mapping, validation, formatting")
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


from enum import Enum

class FieldType(str, Enum):
    NARRATIVE = "narrative"
    LIST = "list"
    TIMELINE = "timeline"
    GROUPED_LIST = "grouped_list"
    STRUCTURED = "structured"
    HYBRID = "hybrid"

class FieldExtractionManifestItem(BaseModel):
    fieldname: str
    meaning: str
    field_type: FieldType
    field_intent: str
    source_hints: str
    content_expectation: str
    structure_expectation: str
    constraints: str
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence in the field semantics (0-1)")
    ambiguity_note: Optional[str] = Field(None, description="Notes on any ambiguity in the field meaning")

from pydantic import model_validator

class TemplateAnalysisResult(BaseModel):
    purpose: str
    expected_sections: str
    field_extraction_manifest: List[FieldExtractionManifestItem]
    global_guidance: str

    @model_validator(mode='before')
    @classmethod
    def no_extra_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            allowed_keys = {'purpose', 'expected_sections', 'field_extraction_manifest', 'global_guidance'}
            extra_keys = set(data.keys()) - allowed_keys
            if extra_keys:
                raise ValueError(f"Unexpected top-level keys found: {extra_keys}")
        return data

class TemplateAsset(BaseModel):
    id: str
    asset_type: str = Field(..., description="template, kb, policy, formatting, example")
    version: str = "1.0.0"
    status: AssetStatus = AssetStatus.DRAFT
    name: str
    description: Optional[str] = None

    # Classification Metadata
    industry: Optional[str] = None
    role_family: Optional[str] = None
    region: Optional[str] = None
    language: str = "en"
    tags: List[str] = Field(default_factory=list)

    # Notes and Guidance
    notes: Optional[str] = None
    purpose: Optional[str] = None
    expected_sections: Optional[str] = None
    expected_fields: Optional[str] = None
    field_extraction_manifest: Optional[List[FieldExtractionManifestItem]] = None

    global_guidance: Optional[str] = None
    analysis_version: Optional[str] = None
    llm_backend: Optional[str] = None
    llm_model_name: Optional[str] = None
    analysis_timestamp: Optional[datetime] = None

    summary_guidance: Optional[str] = None
    formatting_guidance: Optional[str] = None
    validation_guidance: Optional[str] = None
    pii_guidance: Optional[str] = None
    selection_weight: int = 50
    is_default_for_industry: bool = False

    # Provenance and Storage References
    original_file_ref: str
    checksum: str
    extraction_artifact_ref: Optional[str] = None
    render_config_ref: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Extension for provider-specific details
    extension_metadata: Dict[str, Any] = Field(default_factory=dict)
