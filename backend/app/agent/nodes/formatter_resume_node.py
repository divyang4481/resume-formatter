from app.agent.state import AgentState
from app.services.resume_ai_service import ResumeAiService
from app.services.resume_generator_service import ResumeGeneratorService
import json
import logging
import io

logger = logging.getLogger(__name__)


def create_document_composition_node(
    ai_service: ResumeAiService, generator_service: ResumeGeneratorService, storage
):
    """
    Creates the LangGraph node for final document composition.
    Delegates document manipulation to the ResumeGeneratorService.
    """

    async def document_composition_node(state: AgentState) -> dict:
        logger.info("Executing Document Composition Node...")

        session_id = state.get("job_id") or state.get("session_id", "unknown-session")
        summary_text = state.get("summary_text", "")
        summary_uri = state.get("summary_uri", "")
        resume_data = state.get("transformed_document_json") or {}
        template_asset_id = state.get("template_asset_id")
        
        if not template_asset_id:
             logger.warning("No template_asset_id found in state. Falling back to 'MISSING_TEMPLATE_ID'.")
             template_asset_id = "MISSING_TEMPLATE_ID"

        # Initialize return variables
        render_docx_uri = None
        all_missing_fields = state.get("missing_fields") or []
        final_context = {}
        expected_fields_raw = ""
        field_manifest = []

        # 1. Use Summary from state (Assumes upstream generate_cv_summary_node has run)
        if not summary_text:
            logger.warning("Summary text not found in state. Upstream summary generation might have failed.")
            summary_text = "Summary not available."

        # 2. Resolve Template & Render
        try:
            # Resolve Template Bytes
            template_storage_uri = state.get("template_storage_uri")
            template_bytes = None

            # If URI is missing but ID exists, fetch metadata from DB as a single clean fallback
            if not template_storage_uri and template_asset_id != "MISSING_TEMPLATE_ID":
                from app.db.session import SessionLocal
                from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
                
                with SessionLocal() as db:
                    repo = SqlAlchemyTemplateRepository(db)
                    template_meta = repo.get_template(template_asset_id)
                    if template_meta:
                        template_storage_uri = template_meta.storage_uri
                        logger.info(f"Resolved template_storage_uri from DB: {template_storage_uri}")

            if template_storage_uri:
                logger.info(f"Attempting to fetch template from: {template_storage_uri}")
                # Normalize storage key
                template_key = template_storage_uri.replace("local://", "")
                if template_key.startswith("s3://"):
                    from app.config import settings
                    template_key = template_key.replace(f"s3://{settings.s3_bucket_output}/", "")

                try:
                    template_bytes = storage.get_bytes(template_key)
                except Exception as e:
                    logger.error(f"Failed to fetch template from storage key '{template_key}': {e}")

            if not template_bytes:
                raise ValueError(
                    f"Template content not found for ID '{template_asset_id}'. Ensure the template is uploaded and metadata is correct."
                )

            # Prepare Context & Manifest
            if not expected_fields_raw and state.get("selected_template"):
                template_obj = state.get("selected_template")
                if isinstance(template_obj, dict):
                    expected_fields_raw = template_obj.get("expected_fields", "")

            expected_fields_raw = (
                state.get("expected_fields") or expected_fields_raw or ""
            )
            field_manifest = state.get("field_extraction_manifest")
            if isinstance(field_manifest, str):
                try:
                    field_manifest = json.loads(field_manifest)
                except Exception:
                    field_manifest = []
            field_manifest = field_manifest or []

            if resume_data:
                final_context = {
                    **resume_data,
                    "summary": summary_text,
                    "job_id": session_id,
                }
            else:
                final_context = {"summary": summary_text, "job_id": session_id}

            # --- RENDER CONTEXT DUMP ---
            logger.info(
                "\n" + "-" * 60 + "\n--- FINAL RENDERING CONTEXT ---\n" + "-" * 60
            )
            logger.info(
                json.dumps(final_context, indent=2)[:2000] + "..."
                if len(json.dumps(final_context)) > 2000
                else json.dumps(final_context, indent=2)
            )
            logger.info("-" * 60 + "\n")

            # Render Document
            docx_bytes, gen_missing_fields = (
                generator_service.render_formatted_document(
                    template_bytes=template_bytes,
                    resume_data=final_context,
                    expected_fields=expected_fields_raw,
                    field_manifest=field_manifest,
                )
            )

            if gen_missing_fields:
                all_missing_fields = list(set(all_missing_fields + gen_missing_fields))

            render_key = f"jobs/{session_id}/output/formatted_resume.docx"
            render_docx_uri = storage.put_bytes(docx_bytes, render_key)

        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            error_msg = str(e)
            if "NoSuchKey" in error_msg:
                error_msg = f"TEMPLATE MISSING: The file '{template_asset_id}' was not found in S3. Please upload the template in the Admin UI."

            error_docx = generator_service.generate_error_docx(
                template_asset_id, error_msg
            )
            render_key = f"jobs/{session_id}/output/formatted_resume.docx"
            render_docx_uri = storage.put_bytes(error_docx, render_key)

        final_status = "rendered"
        if not state.get("validation_passed", True):
            final_status = "needs_review"

        # 4. Final Cleanup for Web UI Result Item
        from app.agent.utils.llm_sanitizer import LlmSanitizer

        clean_ui_summary = LlmSanitizer.strip_cvml(summary_text)

        return {
            "summary_text": clean_ui_summary,
            "summary_uri": summary_uri,
            "render_docx_uri": render_docx_uri,
            "transformed_document_json": final_context,
            "missing_fields": all_missing_fields,
            "status": final_status,
        }

    return document_composition_node
