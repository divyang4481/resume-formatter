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

    # Provenance and Storage References
    original_file_ref: str
    extraction_artifact_ref: Optional[str] = None
    render_config_ref: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Extension for provider-specific details
    extension_metadata: Dict[str, Any] = Field(default_factory=dict)
