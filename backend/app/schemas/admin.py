from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.enums import AssetStatus

class AssetUploadRequestMetadata(BaseModel):
    asset_type: str = Field(..., description="template, kb, policy, formatting, example")
    template_id: Optional[str] = Field(default=None, description="The ID of the template this asset belongs to")
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    role_family: Optional[str] = None
    region: Optional[str] = None
    language: str = "en"
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    notes: Optional[str] = None
    selection_weight: int = 50
    is_default_for_industry: bool = False

class AssetUploadResponse(BaseModel):
    asset_id: str
    status: AssetStatus
    message: str
