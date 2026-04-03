from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
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

        from datetime import datetime

        return TemplateAsset(
            id=model.id,
            asset_type="template", # Default since we lack it in DB
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
            summary_guidance=model.summary_guidance,

            formatting_guidance=model.formatting_guidance,
            validation_guidance=model.validation_guidance,
            pii_guidance=model.pii_guidance,
            selection_weight=model.selection_weight or 50,
            original_file_ref=model.storage_uri or "",
            checksum=model.checksum_sha256 or "",
            extraction_artifact_ref=model.extraction_uri,
            created_by=model.created_by,
            created_at=model.created_at or datetime.utcnow(),
            updated_at=model.updated_at or datetime.utcnow()
        )

    def save_template(self, template_asset: TemplateAsset) -> str:
        model = self.db.query(TemplateAssetModel).filter(TemplateAssetModel.id == template_asset.id).first()
        if not model:
            model = TemplateAssetModel(id=template_asset.id)
            self.db.add(model)

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
        model.summary_guidance = template_asset.summary_guidance

        model.formatting_guidance = template_asset.formatting_guidance
        model.validation_guidance = template_asset.validation_guidance
        model.pii_guidance = template_asset.pii_guidance
        model.storage_uri = template_asset.original_file_ref
        model.checksum_sha256 = template_asset.checksum
        model.extraction_uri = template_asset.extraction_artifact_ref
        model.created_by = template_asset.created_by
        model.created_at = template_asset.created_at
        model.updated_at = template_asset.updated_at

        self.db.commit()
        return model.id

    def list_templates(self, filters: Dict[str, Any]) -> List[TemplateAsset]:
        query = self.db.query(TemplateAssetModel)

        from sqlalchemy import func

        if "status" in filters:
            query = query.filter(func.lower(TemplateAssetModel.status) == filters["status"].lower())
        if "industry" in filters:
            query = query.filter(func.lower(TemplateAssetModel.industry) == filters["industry"].lower())

        models = query.all()
        results = []
        from datetime import datetime
        for model in models:
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
                    summary_guidance=model.summary_guidance,

                    formatting_guidance=model.formatting_guidance,
                    validation_guidance=model.validation_guidance,
                    pii_guidance=model.pii_guidance,
                    selection_weight=model.selection_weight or 50,
                    original_file_ref=model.storage_uri or "",
                    checksum=model.checksum_sha256 or "",
                    extraction_artifact_ref=model.extraction_uri,
                    created_by=model.created_by,
                    created_at=model.created_at or datetime.utcnow(),
                    updated_at=model.updated_at or datetime.utcnow()
                )
            )
        return results
