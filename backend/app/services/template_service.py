import hashlib
import uuid
from datetime import datetime
from typing import Optional

from app.domain.interfaces import StorageProvider, TemplateRepository, EventBus
from app.schemas.template import TemplateAsset
from app.schemas.admin import AssetUploadRequestMetadata
from app.schemas.events import AssetUploadedEvent
from app.schemas.enums import AssetStatus

class TemplateService:
    def __init__(
        self,
        storage_provider: StorageProvider,
        template_repository: TemplateRepository,
        event_bus: EventBus
    ):
        self.storage_provider = storage_provider
        self.template_repository = template_repository
        self.event_bus = event_bus

    async def upload_asset(self, filename: str, content: bytes, metadata: AssetUploadRequestMetadata, uploaded_by: str = "system") -> str:
        """
        Handles the logic for uploading a template asset:
        - Stores the asset
        - Computes checksum
        - Saves draft metadata
        - Emits an audit event
        """
        # 1. Compute checksum
        checksum = hashlib.sha256(content).hexdigest()

        # 2. Generate unique asset ID
        asset_id = str(uuid.uuid4())

        # 3. Store asset
        storage_key = f"templates/{asset_id}/{filename}"
        storage_uri = self.storage_provider.put_bytes(storage_key, content)

        # 4. Save metadata record (draft)
        template_asset = TemplateAsset(
            id=asset_id,
            asset_type=metadata.asset_type,
            name=metadata.name,
            description=metadata.description,
            industry=metadata.industry,
            role_family=metadata.role_family,
            region=metadata.region,
            language=metadata.language,
            tags=metadata.tags,
            version=metadata.version,
            status=AssetStatus.DRAFT,
            original_file_ref=storage_uri,
            checksum=checksum,
            created_by=uploaded_by
        )
        self.template_repository.save_template(template_asset)

        # 5. Emit Audit Event
        event = AssetUploadedEvent(
            asset_id=asset_id,
            asset_type=metadata.asset_type,
            filename=filename,
            storage_uri=storage_uri,
            checksum=checksum,
            uploaded_at=datetime.utcnow(),
            metadata=metadata.model_dump()
        )
        self.event_bus.publish("template_asset.uploaded", event.model_dump())

        # 6. Record in Audit Log
        self.event_bus.audit(
            action="asset_uploaded",
            details={
                "asset_id": asset_id,
                "user": uploaded_by,
                "filename": filename,
                "checksum": checksum,
                "storage_uri": storage_uri
            }
        )

        return asset_id
