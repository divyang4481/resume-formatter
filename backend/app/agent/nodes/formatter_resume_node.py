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
        template_id = state.get("selected_template_id") or state.get("template_asset_id") or "MISSING_TEMPLATE_ID"
        
        # Initialize return variables
        render_docx_uri = None
        all_missing_fields = state.get("missing_fields") or []
        final_context = {}
        expected_fields_raw = ""
        field_manifest = []

        # 1. Generate Summary if not already present
        try:
            extracted_text = state.get("extracted_text", "")
            if not summary_text or summary_text == "Summary not available.":
                if extracted_text:
                    summary_guidance = state.get("summary_guidance") or ""
                    industry = state.get("industry")
                    language = state.get("language", "en")

                    # Use AI Service for summary
                    summary_text = await ai_service.generate_summary(
                        extracted_text=extracted_text,
                        guidance=summary_guidance,
                        industry=industry,
                        language=language,
                    )
                else:
                    summary_text = "Original resume text not found. Summary cannot be generated."
            
            # Save Summary Artifact
            summary_key = f"jobs/{session_id}/output/summary.md"
            final_summary_md = f"### CV Summary\n\n{summary_text}"
            summary_uri = storage.put_bytes(final_summary_md.encode("utf-8"), summary_key)
            
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            summary_text = summary_text or "Summary generation failed."

        # 2. Resolve Template & Render
        try:
            # Resolve Template Bytes
            template_storage_uri = state.get("template_storage_uri")
            if template_storage_uri:
                template_key = template_storage_uri.replace("local://", "")
            else:
                from app.config import settings
                if settings.storage_provider == "s3":
                    template_key = f"s3://{settings.s3_bucket_output}/templates/{template_id}/template.docx"
                else:
                    template_key = f"templates/{template_id}/template.docx"
            
            try:
                template_bytes = storage.get_bytes(template_key)
            except Exception as s3_err:
                logger.warning(f"Template {template_id} not found: {s3_err}")
                raise s3_err

            # Prepare Context & Manifest
            if not expected_fields_raw and state.get("selected_template"):
                template_obj = state.get("selected_template")
                if isinstance(template_obj, dict):
                    expected_fields_raw = template_obj.get("expected_fields", "")
            
            expected_fields_raw = state.get("expected_fields") or expected_fields_raw or ""
            field_manifest = state.get("field_extraction_manifest") or []
            
            if resume_data:
                final_context = {**resume_data, "summary": summary_text, "job_id": session_id}
            else:
                final_context = {"summary": summary_text, "job_id": session_id}

            # --- RENDER CONTEXT DUMP ---
            logger.info("\n" + "-"*60 + "\n--- FINAL RENDERING CONTEXT ---\n" + "-"*60)
            logger.info(json.dumps(final_context, indent=2)[:2000] + "..." if len(json.dumps(final_context)) > 2000 else json.dumps(final_context, indent=2))
            logger.info("-"*60 + "\n")

            # Render Document
            docx_bytes, gen_missing_fields = generator_service.render_formatted_document(
                template_bytes=template_bytes,
                resume_data=final_context,
                expected_fields=expected_fields_raw,
                field_manifest=field_manifest,
            )
            
            if gen_missing_fields:
                all_missing_fields = list(set(all_missing_fields + gen_missing_fields))

            render_key = f"jobs/{session_id}/output/formatted_resume.docx"
            render_docx_uri = storage.put_bytes(docx_bytes, render_key)

        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            error_msg = str(e)
            if "NoSuchKey" in error_msg:
                error_msg = f"TEMPLATE MISSING: The file '{template_id}' was not found in S3. Please upload the template in the Admin UI."
            
            error_docx = generator_service.generate_error_docx(template_id, error_msg)
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
