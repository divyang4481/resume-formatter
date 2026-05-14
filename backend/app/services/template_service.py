import hashlib
import uuid
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

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
        knowledge_index: Optional[KnowledgeIndex] = None,
        template_analysis_service: Optional['TemplateAnalysisService'] = None
    ):
        self.storage_provider = storage_provider
        self.template_repository = template_repository
        self.event_bus = event_bus
        self.extraction_service = extraction_service
        self.knowledge_index = knowledge_index
        self.template_analysis_service = template_analysis_service

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
        storage_uri = self.storage_provider.put_bytes(content, storage_key)

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
            
            logger.info("\n" + "=" * 60 + "\n--- DOCLING EXTRACTION RESULT (Knowledge Asset) ---\n" + "=" * 60)
            logger.info(extracted_doc.extracted_text or "No text extracted")
            logger.info("=" * 60 + "\n")
            
            extracted_text = extracted_doc.extracted_text
            backend_used = extracted_doc.backend_used

            # Simple indexing stub, add correct chunk metadata
            # Important: The template ID must be the actual template_id provided in metadata.
            # If a knowledge asset is uploaded without a template_id, we fall back to asset_id
            # but ideally it should always be provided by the caller to tie to the Template parent.
            actual_template_id = metadata.template_id or asset_id

            chunk_metadata = {
                "template_id": actual_template_id,
                "asset_id": asset_id,
                "asset_type": metadata.asset_type,
                "status": "draft",  # Starts as DRAFT
                "industry": metadata.industry,
                "role_family": metadata.role_family,
                "language": metadata.language,
                "source_kind": metadata.asset_type
            }

            self.knowledge_index.index_chunks(
                chunks=[{"text": extracted_text, **chunk_metadata}],
                asset_id=asset_id
            )

        # 4b. If it is a template, analyze it for suggestions to pre-fill draft
        suggestions = {}
        if metadata.asset_type == "template_docx" and self.template_analysis_service:
            try:
                # --- CACHE CHECK: SHA-256 ---
                existing_asset = self.template_repository.get_by_checksum(checksum)
                if existing_asset and existing_asset.field_extraction_manifest:
                    logger.info(f"[Cache Hit] Reusing manifest for template with checksum: {checksum}")
                    # We create a dummy object that mimics the TemplateAnalysis result structure
                    from types import SimpleNamespace
                    suggestions = SimpleNamespace(
                        purpose=existing_asset.purpose,
                        expected_sections=existing_asset.expected_sections,
                        expected_fields=existing_asset.expected_fields,
                        fields=existing_asset.field_extraction_manifest,
                        summary_guidance=existing_asset.summary_guidance,
                        formatting_guidance=existing_asset.formatting_guidance,
                        validation_guidance=existing_asset.validation_guidance,
                        pii_guidance=existing_asset.pii_guidance,
                        model_dump_json=lambda: existing_asset.analysis_json if hasattr(existing_asset, 'analysis_json') else "{}"
                    )
                else:
                    logger.info(f"Triggering automatic AI analysis for template: {filename}")
                    suggestions = await self.template_analysis_service.analyze_template(content, filename)
                
                if suggestions:
                    logger.info(f"--- [AI TEMPLATE INSIGHTS: {filename}] ---")
                    # Use getattr as suggestions might be a SimpleNamespace (cache hit) or a Pydantic model (fresh analysis)
                    purpose = getattr(suggestions, "purpose", "Unknown")
                    print(f"EXPECTED SECTIONS: {getattr(suggestions, 'expected_sections', 'None')}")
                    manifest = getattr(suggestions, "fields", [])
                    print(f"IDENTIFIED MANIFEST FIELDS: {len(manifest)}")
                    
                    # BACKWARD COMPATIBILITY: Sync expected_fields from manifest if missing
                    if manifest and not getattr(suggestions, "expected_fields", None):
                        # suggestions might be SimpleNamespace so we might need to set it
                        if isinstance(suggestions, SimpleNamespace):
                            suggestions.expected_fields = ", ".join([f.get("fieldname") for f in manifest if f.get("fieldname")])
                        else:
                            # If it's a model, it might be immutable or have different setter
                            pass 
                    
                    print(f"EXPECTED FIELDS SUMMARY: {getattr(suggestions, 'expected_fields', 'None')}")
                    print(f"-------------------------------------------")

            except Exception as analysis_err:
                logger.error(f"Auto-analysis failed during upload, but continuing with default draft: {analysis_err}")

        def ensure_str(val):
            if val is None:
                return None
            if isinstance(val, (dict, list)):
                import json
                return json.dumps(val)
            return str(val)

        # 5. Save metadata record (draft)
        template_asset = TemplateAsset(
            id=asset_id,
            asset_type=metadata.asset_type,
            name=getattr(suggestions, "purpose", metadata.name or filename),
            description=metadata.description,
            industry=metadata.industry,
            role_family=metadata.role_family,
            region=metadata.region,
            language=metadata.language,
            tags=metadata.tags,
            version=metadata.version,
            status=AssetStatus.DRAFT,
            purpose=ensure_str(getattr(suggestions, "purpose", None)),
            expected_sections=ensure_str(getattr(suggestions, "expected_sections", None)),
            expected_fields=ensure_str(getattr(suggestions, "expected_fields", None)),
            field_extraction_manifest=getattr(suggestions, "fields", []), # Use .fields from TemplateAnalysis
            summary_guidance=ensure_str(getattr(suggestions, "summary_guidance", None)),
            formatting_guidance=ensure_str(getattr(suggestions, "formatting_guidance", None)),
            validation_guidance=ensure_str(getattr(suggestions, "validation_guidance", None)),
            pii_guidance=ensure_str(getattr(suggestions, "pii_guidance", None)),
            complexity_score=getattr(suggestions, "complexity_score", 0.0),
            model_usage_json=getattr(suggestions, "model_usage_json", {}),
            llm_attempt_count=getattr(suggestions, "llm_attempt_count", 0),
            requires_human_review=getattr(suggestions, "human_review_required", False),
            storage_uri=storage_uri,
            checksum=checksum,
            created_by=uploaded_by,
            analysis_json=suggestions.model_dump_json() if hasattr(suggestions, 'model_dump_json') else ensure_str(suggestions),
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
