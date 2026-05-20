from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import json
from datetime import datetime

from app.db.models import TemplateAsset as TemplateAssetModel
from app.schemas.template import TemplateAsset
from app.domain.interfaces import TemplateRepository
from app.schemas.enums import AssetStatus


class SqlAlchemyTemplateRepository(TemplateRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_template(self, template_id: str, version: Optional[str] = None) -> Optional[TemplateAsset]:
        query = self.db.query(TemplateAssetModel).filter(TemplateAssetModel.id == template_id)
        if version:
            query = query.filter(TemplateAssetModel.version == version)
        model = query.first()
        if not model:
            return None
        # Deserialize manifest if present
        manifest_data = None
        if model.field_extraction_manifest:
            try:
                manifest_data = json.loads(model.field_extraction_manifest)
                if not isinstance(manifest_data, list):
                    manifest_data = None
            except Exception:
                manifest_data = None
        return TemplateAsset(
            id=model.id,
            asset_type="template",
            name=model.name,
            version=model.version,
            status=AssetStatus(model.status.lower()),
            industry=model.industry,
            role_family=model.role_family,
            region=model.region,
            language=model.language or "en",
            notes=model.notes,
            purpose=model.purpose,
            expected_sections=model.expected_sections,
            expected_fields=model.expected_fields,
            field_extraction_manifest=manifest_data,
            summary_guidance=model.summary_guidance,
            docling_extraction=model.docling_extraction,
            formatting_guidance=model.formatting_guidance,
            validation_guidance=model.validation_guidance,
            pii_guidance=model.pii_guidance,
            selection_weight=model.selection_weight or 50,
            storage_uri=model.storage_uri or "",
            checksum=model.checksum_sha256 or "",
            extraction_uri=model.extraction_uri,
            created_by=model.created_by,
            created_at=model.created_at or datetime.utcnow(),
            updated_at=model.updated_at or datetime.utcnow(),
            analysis_json=model.analysis_json,
        )

    def save_template(self, template_asset: TemplateAsset) -> str:
        model = self.db.query(TemplateAssetModel).filter(TemplateAssetModel.id == template_asset.id).first()
        if not model:
            model = TemplateAssetModel(id=template_asset.id)
            self.db.add(model)
        # Map fields
        model.name = template_asset.name
        model.version = template_asset.version
        model.status = template_asset.status.value.upper()
        model.industry = template_asset.industry
        model.role_family = template_asset.role_family
        model.region = template_asset.region
        model.language = template_asset.language
        model.notes = template_asset.notes
        model.purpose = template_asset.purpose
        model.expected_sections = template_asset.expected_sections
        model.expected_fields = template_asset.expected_fields
        # Serialize manifest
        if template_asset.field_extraction_manifest:
            model.field_extraction_manifest = json.dumps([item.model_dump() for item in template_asset.field_extraction_manifest])
        else:
            model.field_extraction_manifest = None
        model.summary_guidance = template_asset.summary_guidance
        model.docling_extraction = getattr(template_asset, "docling_extraction", None)
        model.formatting_guidance = template_asset.formatting_guidance
        model.validation_guidance = template_asset.validation_guidance
        model.pii_guidance = template_asset.pii_guidance
        model.storage_uri = template_asset.storage_uri
        model.checksum_sha256 = template_asset.checksum
        model.extraction_uri = template_asset.extraction_uri
        model.created_by = template_asset.created_by
        model.created_at = template_asset.created_at
        model.updated_at = template_asset.updated_at
        model.analysis_json = template_asset.analysis_json
        self.db.commit()
        return model.id

    def list_templates(self, filters: Dict[str, Any]) -> List[TemplateAsset]:
        query = self.db.query(TemplateAssetModel)
        if "status" in filters:
            query = query.filter(func.lower(TemplateAssetModel.status) == filters["status"].lower())
        if "industry" in filters:
            query = query.filter(func.lower(TemplateAssetModel.industry) == filters["industry"].lower())
        models = query.all()
        results: List[TemplateAsset] = []
        for model in models:
            manifest_data = None
            if model.field_extraction_manifest:
                try:
                    manifest_data = json.loads(model.field_extraction_manifest)
                    if not isinstance(manifest_data, list):
                        manifest_data = None
                except Exception:
                    manifest_data = None
            results.append(
                TemplateAsset(
                    id=model.id,
                    asset_type="template",
                    name=model.name,
                    version=model.version,
                    status=AssetStatus(model.status.lower()),
                    industry=model.industry,
                    role_family=model.role_family,
                    region=model.region,
                    language=model.language or "en",
                    notes=model.notes,
                    purpose=model.purpose,
                    expected_sections=model.expected_sections,
                    expected_fields=model.expected_fields,
                    field_extraction_manifest=manifest_data,
                    summary_guidance=model.summary_guidance,
                    docling_extraction=model.docling_extraction,
                    formatting_guidance=model.formatting_guidance,
                    validation_guidance=model.validation_guidance,
                    pii_guidance=model.pii_guidance,
                    selection_weight=model.selection_weight or 50,
                    storage_uri=model.storage_uri or "",
                    checksum=model.checksum_sha256 or "",
                    extraction_uri=model.extraction_uri,
                    created_by=model.created_by,
                    created_at=model.created_at or datetime.utcnow(),
                    updated_at=model.updated_at or datetime.utcnow(),
                    analysis_json=model.analysis_json,
                )
            )
        return results

    def list_active_templates(self) -> List[TemplateAsset]:
        return self.list_templates(filters={"status": "active"})

    def get_by_checksum(self, checksum: str) -> Optional[TemplateAsset]:
        model = self.db.query(TemplateAssetModel).filter(TemplateAssetModel.checksum_sha256 == checksum).first()
        if not model:
            return None
        return self.get_template(model.id)
