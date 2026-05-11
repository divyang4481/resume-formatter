from app.agent.state import AgentState
from app.services.resume_ai_service import ResumeAiService
from app.services.resume_generator_service import ResumeGeneratorService
import json
import logging
import io

logger = logging.getLogger(__name__)


def create_render_node(
    ai_service: ResumeAiService, generator_service: ResumeGeneratorService, storage
):
    """
    Creates the LangGraph node for rendering the final outputs.
    Delegates document manipulation to the ResumeGeneratorService.
    """

    async def render_node(state: AgentState) -> dict:
        logger.info("Executing Formatter Resume Node...")

        extracted_text = state.get("extracted_text", "")
        transformed_json_str = state.get("transformed_document_json", "")
        session_id = state.get("session_id", "unknown-session")
        summary_text = "Summary not available."
        resume_data = {}

        # 1. Prepare Data & Summary
        try:
            if transformed_json_str:
                if isinstance(transformed_json_str, dict):
                    resume_data = transformed_json_str
                else:
                    resume_data = json.loads(transformed_json_str)

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
                summary_text = (
                    "Original resume text not found. Summary cannot be generated."
                )
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            summary_text = "Summary generation failed."

        # 1. Safe Debug Logging
        state_keys = list(state.keys())
        logger.info(f"Render Node State Keys: {state_keys}")
        logger.info(f"Attempting to resolve template. Selected Template ID in state: {state.get('selected_template_id')}, Template Asset ID: {state.get('template_asset_id')}")

        # 2. Save Summary Artifact
        summary_key = f"jobs/{session_id}/output/summary.md"
        final_summary_md = f"### CV Summary\n\n{summary_text}"
        summary_uri = storage.put_bytes(final_summary_md.encode("utf-8"), summary_key)

        # 3. Resolve Template Identifier
        template_id = state.get("selected_template_id") or state.get("template_asset_id")
        
        if not template_id and state.get("selected_template"):
            # Handle cases where the full template object is in the state
            template_obj = state.get("selected_template")
            if isinstance(template_obj, dict):
                template_id = template_obj.get("id") or template_obj.get("template_asset_id")
        
        template_id = template_id or "MISSING_TEMPLATE_ID"
        template_storage_uri = state.get("template_storage_uri")
        render_docx_uri = None

        # 4. Document Rendering
        render_key = f"jobs/{session_id}/output/formatted_resume.docx"
        try:
            # Resolve template path
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
                # Re-raise to trigger the error document fallback below
                raise s3_err

            # Linearize and polish JSON data for the template style via AI
            if resume_data:
                template_text_content = state.get("template_text") or ""
                formatting_guidance = state.get("formatting_guidance") or ""

                # ... (rest of harmonization logic)
                expected_fields_raw = state.get("expected_fields")
                if not expected_fields_raw and state.get("selected_template"):
                    template_obj = state.get("selected_template")
                    if isinstance(template_obj, dict):
                        expected_fields_raw = template_obj.get("expected_fields", "")
                expected_fields_raw = expected_fields_raw or ""
                
                detected_placeholders = [f.strip() for f in expected_fields_raw.split(",") if f.strip()]
                field_manifest = state.get("field_extraction_manifest")
                
                formatted_data = await ai_service.harmonize_data_to_template_style(
                    structured_data=resume_data,
                    template_text=template_text_content,
                    detected_placeholders=detected_placeholders,
                    field_manifest=field_manifest,
                    formatting_guidance=formatting_guidance,
                )
                # Only use the polished, harmonized data for the final document to prevent redundancy
                final_context = {**formatted_data, "summary": summary_text, "job_id": session_id}
            else:
                final_context = {**resume_data, "summary": summary_text, "job_id": session_id}

            # --- RENDER CONTEXT DUMP ---
            logger.info("\n" + "-"*60 + "\n--- FINAL RENDERING CONTEXT ---\n" + "-"*60)
            logger.info(json.dumps(final_context, indent=2)[:2000] + "..." if len(json.dumps(final_context)) > 2000 else json.dumps(final_context, indent=2))
            logger.info("-"*60 + "\n")

            docx_bytes, gen_missing_fields = generator_service.render_formatted_document(
                template_bytes=template_bytes,
                resume_data=final_context,
                expected_fields=expected_fields_raw,
                field_manifest=field_manifest,
            )
            
            # Merge missing fields discovered during rendering into state
            if gen_missing_fields:
                state_missing = state.get("missing_fields") or []
                unique_missing = list(set(state_missing + gen_missing_fields))
                state["missing_fields"] = unique_missing

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
            "status": final_status,
        }

    return render_node
