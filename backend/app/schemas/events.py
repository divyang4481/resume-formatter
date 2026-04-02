from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

class AssetUploadedEvent(BaseModel):
    asset_id: str
    asset_type: str
    filename: str
    storage_uri: str
    checksum: str
    uploaded_at: datetime
    metadata: Dict[str, Any]
