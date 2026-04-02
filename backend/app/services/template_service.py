import hashlib
import uuid
from datetime import datetime
from typing import Optional

from app.domain.interfaces import StorageProvider, TemplateRepository, EventBus, DocumentExtractionService, KnowledgeIndex, ExtractionContext
from app.schemas.template import TemplateAsset
from app.schemas.admin import AssetUploadRequestMetadata
from app.schemas.events import AssetUploadedEvent
from app.schemas.enums import AssetStatus

class TemplateService:
    def __init__(
        self,
        storage_provider: StorageProvider,
        template_repository: TemplateRepository,
        event_bus: EventBus,
        extraction_service: Optional[DocumentExtractionService] = None,
        knowledge_index: Optional[KnowledgeIndex] = None
    ):
        self.storage_provider = storage_provider
        self.template_repository = template_repository
        self.event_bus = event_bus
        self.extraction_service = extraction_service
        self.knowledge_index = knowledge_index

    async def upload_asset(self, filename: str, content: bytes, metadata: AssetUploadRequestMetadata, content_type: str, uploaded_by: str = "system") -> str:
        """
        Handles the logic for uploading a template asset:
        - Stores the asset
        - Computes checksum
        - Saves draft metadata
        - If knowledge-bearing, extracts text and indexes it
        - Emits an audit event
        """
        # 1. Compute checksum
        checksum = hashlib.sha256(content).hexdigest()

        # 2. Generate unique asset ID
        asset_id = str(uuid.uuid4())

        # 3. Store asset
        storage_key = f"templates/{asset_id}/{filename}"
        storage_uri = self.storage_provider.put_bytes(storage_key, content)

        # 4. Extract and Index if Knowledge-bearing
        # Only extract if it is a knowledge asset, not a structured template shell/rule
        knowledge_bearing_kinds = {"sample_resume", "guidance_pdf", "policy_doc"}
        structured_template_kinds = {"template_docx", "template_json", "template_yaml"}

        extracted_text = None
        backend_used = None

        if metadata.asset_type in knowledge_bearing_kinds and self.extraction_service and self.knowledge_index:
            context = ExtractionContext(intent="template_knowledge", actor_role=uploaded_by)
            extracted_doc = await self.extraction_service.extract(
                file_bytes=content,
                filename=filename,
                content_type=content_type,
                context=context
            )
            extracted_text = extracted_doc.extracted_text
            backend_used = extracted_doc.backend_used

            # Simple indexing stub
            self.knowledge_index.index_chunks(
                chunks=[{"text": extracted_text}],
                asset_id=asset_id
            )

        # 5. Save metadata record (draft)
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
            created_by=uploaded_by,
            extension_metadata={"document_extractor_backend": backend_used} if backend_used else {}
        )
        self.template_repository.save_template(template_asset)

        # 6. Emit Audit Event
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
