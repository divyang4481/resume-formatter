from typing import Any, Dict, List, Optional, Union
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


class FieldExtractionManifestItem(BaseModel):
    fieldname: str
    marker_text: str
    meaning: str
    source_hints: Union[str, List[str]]
    field_type: str = "scalar"
    canonical_fieldname: Optional[str] = None
    original_label: Optional[str] = None
    resume_fillable: bool = True
    source_kind: str = "resume_fact"
    required: bool = False
    confidence: float = 0.0
    occurrence_index: int = 1
    context: Dict[str, Any] = Field(default_factory=dict)
    extraction_hints: Dict[str, Any] = Field(default_factory=dict)
    injection_hints: Dict[str, Any] = Field(default_factory=dict)
    render_locator: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    sub_fields: List[Dict[str, Any]] = Field(default_factory=list)

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

    summary_guidance: Optional[str] = None
    docling_extraction: Optional[str] = None  # Raw Docling extraction output
    formatting_guidance: Optional[str] = None
    validation_guidance: Optional[str] = None
    pii_guidance: Optional[str] = None
    selection_weight: int = 50
    is_default_for_industry: bool = False

    # Provenance and Storage References
    storage_uri: str
    checksum: str
    extraction_uri: Optional[str] = None
    render_config_ref: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Full analysis payload (includes raw_structure)
    analysis_json: Optional[str] = None

    # Extension for provider-specific details
    extension_metadata: Dict[str, Any] = Field(default_factory=dict)


class TemplateTestRun(BaseModel):
    id: str
    template_id: str
    sample_resume_asset_id: Optional[str] = None
    processing_job_id: str
    decision: Optional[str] = None
    review_notes: Optional[str] = None
    generated_summary: Optional[str] = None
    output_doc_path: Optional[str] = None
    output_pdf_path: Optional[str] = None
    extracted_json_path: Optional[str] = None
    validation_result_json: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

