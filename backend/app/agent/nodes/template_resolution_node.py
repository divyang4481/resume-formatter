import asyncio
import os
import json
import logging
import re
from app.agent.state import AgentState
from app.domain.interfaces import LlmRuntimeAdapter
from app.db.session import SessionLocal
from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
from app.services.template_resolution_service import TemplateResolutionService
from app.services.resume_ai_service import ResumeAiService
from app.domain.interfaces import LlmRuntimeAdapter

logger = logging.getLogger(__name__)

def create_template_resolve_node(llm_runtime, storage_provider, doc_parser):
    """
    Creates the LangGraph node for resolving the appropriate template based on the
    document content or user request.
    """
    async def template_resolve_node(state: AgentState) -> dict:
        logger.info(f"Executing Template Resolution Node (Job ID: {state.get('session_id')})...")
        
        from app.domain.interfaces import ExtractionContext
        
        extracted_text = state.get("extracted_text", "")
        requested_template_id = state.get("template_asset_id")
        
        template_asset_id = requested_template_id
        storage_uri = None
        summary_guidance = None
        formatting_guidance = None
        validation_guidance = None
        pii_guidance = None
        expected_sections = state.get("expected_sections")
        expected_fields = state.get("expected_fields")
        field_manifest = state.get("field_extraction_manifest")
        
        # Ensure field_manifest is a list if it came in as a JSON string
        if isinstance(field_manifest, str):
            try:
                field_manifest = json.loads(field_manifest)
            except Exception:
                field_manifest = []
        template_text = ""

        db = SessionLocal()
        try:
            repo = SqlAlchemyTemplateRepository(db)
            
            # Phase 1: Validate or Identify Template
            template_meta = None
            if template_asset_id:
                # User requested a specific template, verify it exists
                template_meta = repo.get_template(template_asset_id)
                if not template_meta:
                    logger.warning(f"Requested template ID '{template_asset_id}' NOT FOUND in database. Falling back to recommendation.")
                    template_asset_id = None

            if not template_asset_id:
                # Dynamic recommendation
                resolution_service = TemplateResolutionService(llm_runtime, repo)
                result = await resolution_service.recommend_template(
                    extracted_text=extracted_text,
                    mode=state.get("intent", "recruiter_runtime")
                )
                template_asset_id = result.template_asset_id
                
                if template_asset_id:
                    template_meta = repo.get_template(template_asset_id)
                    logger.info(f"Recommended Template ID: {template_asset_id}")
                
            # Final Fallback: First active template
            if not template_meta:
                active_templates = repo.list_active_templates()
                if active_templates:
                    template_meta = active_templates[0]
                    template_asset_id = template_meta.id
                    logger.info(f"Using Default Fallback Template: {template_asset_id}")
                else:
                    # Critical failure: no templates at all
                    logger.error("DATABASE ERROR: No active templates found in the system.")
                    raise ValueError("DATABASE ERROR: No active templates found in the system. Please upload a template via the Admin UI.")

            # Phase 2: Populate Metadata from verified record
            storage_uri = template_meta.storage_uri
            summary_guidance = template_meta.summary_guidance
            formatting_guidance = template_meta.formatting_guidance
            validation_guidance = template_meta.validation_guidance
            pii_guidance = template_meta.pii_guidance
            expected_sections = template_meta.expected_sections
            expected_fields = template_meta.expected_fields
            
            # Fetch the manifest (JSON)
            if template_meta.field_extraction_manifest:
                try:
                    if isinstance(template_meta.field_extraction_manifest, str):
                        field_manifest = json.loads(template_meta.field_extraction_manifest)
                    else:
                        # Ensure it's a list of dicts even if it's a list of Pydantic models
                        field_manifest = [
                            m.dict() if hasattr(m, "dict") else m 
                            for m in template_meta.field_extraction_manifest
                        ]
                except Exception as e:
                    logger.error(f"Failed to parse manifest for {template_asset_id}: {e}")
                    field_manifest = field_manifest or []

            if field_manifest:
                logger.info(f"Successfully resolved manifest with {len(field_manifest)} fields for template {template_asset_id}")
            else:
                logger.warning(f"No manifest found in DB for template {template_asset_id}")

            # Phase 3: Extract Text & Analyze On-the-fly if needed
            content = None
            if storage_uri:
                try:
                    storage_key = storage_uri.replace("local://", "")
                    # Strip s3:// prefix if present
                    if storage_key.startswith("s3://"):
                        from app.config import settings
                        storage_key = storage_key.replace(f"s3://{settings.s3_bucket_output}/", "")

                    content = storage_provider.get_bytes(storage_key)
                    
                    context = ExtractionContext(intent="template_context_extraction", actor_role="system")
                    extracted_doc = await doc_parser.extract(
                        file_bytes=content,
                        filename="template.docx",
                        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        context=context
                    )
                    template_text = extracted_doc.extracted_text
                    
                    # --- AUTO-DISCOVERY: If DB is missing fields, find them in the docx text ---
                    if not expected_fields and template_text:
                        placeholders = re.findall(r'«([^»]+)»|\[([^\]]+)\]', template_text)
                        # Flatten matches from groups
                        flat_placeholders = []
                        for m in placeholders:
                            flat_placeholders.extend([i for i in m if i])
                        if flat_placeholders:
                            expected_fields = ",".join(list(set(flat_placeholders)))

                    # --- ON-THE-FLY ANALYSIS: If manifest is missing, generate it now ---
                    if not field_manifest and content:
                        logger.info(f"Manifest missing for template {template_asset_id}. Triggering on-the-fly analysis...")
                        try:
                            ai_service = ResumeAiService(llm_runtime, doc_parser)
                            analysis = await ai_service.analyze_template(content=content, filename="template.docx")
                            if analysis and "field_extraction_manifest" in analysis:
                                field_manifest = analysis["field_extraction_manifest"]
                                # Save back to DB to persist this analysis
                                try:
                                    template_meta.field_extraction_manifest = json.dumps(field_manifest)
                                    repo.save_template(template_meta)
                                    db.commit()
                                except Exception as db_err:
                                    logger.warning(f"Non-critical: Failed to save on-the-fly manifest: {db_err}")
                        except Exception as ai_err:
                            logger.error(f"Failed on-the-fly template analysis: {ai_err}")

                except Exception as ex:
                    logger.error(f"Failed to extract raw text from template {template_asset_id}: {ex}")

            return {
                "template_asset_id": template_asset_id,
                "template_storage_uri": storage_uri,
                "template_text": template_text,
                "summary_guidance": summary_guidance,
                "formatting_guidance": formatting_guidance,
                "validation_guidance": validation_guidance,
                "pii_guidance": pii_guidance,
                "expected_sections": expected_sections,
                "expected_fields": expected_fields,
                "field_extraction_manifest": field_manifest,
                "status": "template_resolved"
            }

        except Exception as e:
            logger.error(f"CRITICAL ERROR during template resolution: {e}")
            # Even in fallback, we must return a state that allows downstream nodes to function or fail gracefully
            return {
                "status": "template_resolution_failed",
                "error_message": str(e)
            }
        finally:
            db.close()

    return template_resolve_node
