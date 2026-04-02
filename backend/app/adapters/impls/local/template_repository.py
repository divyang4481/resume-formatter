from typing import Any, Dict, List, Optional
from app.domain.interfaces import TemplateRepository
from app.schemas.template import TemplateAsset

class InMemoryTemplateRepository(TemplateRepository):
    def __init__(self):
        self._assets: Dict[str, TemplateAsset] = {}

    def get_template(self, template_id: str, version: Optional[str] = None) -> Optional[TemplateAsset]:
        # Simple lookup by ID for now, ignoring versioning logic to keep it minimal
        return self._assets.get(template_id)

    def save_template(self, template_asset: TemplateAsset) -> str:
        self._assets[template_asset.id] = template_asset
        return template_asset.id

    def list_templates(self, filters: Dict[str, Any]) -> List[TemplateAsset]:
        # Minimal list logic returning everything, add filter logic if needed
        return list(self._assets.values())
