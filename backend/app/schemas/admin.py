from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.enums import AssetStatus

class AssetUploadRequestMetadata(BaseModel):
    asset_type: str = Field(..., description="template, kb, policy, formatting, example")
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    role_family: Optional[str] = None
    region: Optional[str] = None
    language: str = "en"
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0.0"

class AssetUploadResponse(BaseModel):
    asset_id: str
    status: AssetStatus
    message: str
