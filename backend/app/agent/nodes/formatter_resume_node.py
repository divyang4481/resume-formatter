from app.agent.state import AgentState
from app.services.resume_ai_service import ResumeAiService
from app.services.resume_generator_service import ResumeGeneratorService
from app.services.audit_service import AuditService
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
        logger.info(f"Executing Formatter Resume Node (Session ID: {state.get('session_id')})...")
        logger.info(f"Available State Keys: {list(state.keys())}")

        extracted_text = state.get("extracted_text", "")
        transformed_json_str = state.get("transformed_document_json", "")
        session_id = state.get("session_id", "unknown-session")
        summary_text = "Summary not available."
        resume_data = {}

        # 1. Prepare Data & Summary
        try:
            if transformed_json_str:
                from app.agent.utils.llm_sanitizer import LlmSanitizer
                cleaned_transformed = LlmSanitizer.clean_json(transformed_json_str)
                resume_data = json.loads(cleaned_transformed)

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
                    job_id=session_id
                )

            else:
                summary_text = (
                    "Original resume text not found. Summary cannot be generated."
                )
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            summary_text = "Summary generation failed."

        # 2. Save Summary Artifact
        summary_key = f"jobs/{session_id}/output/summary.md"
        final_summary_md = f"### CV Summary\n\n{summary_text}"
        summary_uri = storage.put_bytes(summary_key, final_summary_md.encode("utf-8"))

        template_id = state.get("selected_template_id") or "general_cv_v1"
        template_storage_uri = state.get("template_storage_uri")
        render_docx_uri = None

        # 3. Document Rendering
        try:
            if not template_storage_uri:
                logger.warning(f"No template_storage_uri in state. Falling back to ID guess for {template_id}")
                template_key = f"templates/{template_id}/template.docx"
            else:
                template_key = template_storage_uri.replace("local://", "")

            logger.info(f"Loading template from storage key: {template_key}")
            template_bytes = storage.get_bytes(template_key)

            # Linearize and polish JSON data for the template style via AI
            if resume_data:
                template_text_content = state.get("template_text") or ""
                formatting_guidance = state.get("formatting_guidance") or ""

                # Retrieve target placeholders and manifest from state
                expected_fields_raw = state.get("expected_fields") or ""
                detected_placeholders = [
                    f.strip() for f in expected_fields_raw.split(",") if f.strip()
                ]
                field_manifest = state.get("field_extraction_manifest")

                logger.info(
                    f"Harmonizing {len(resume_data)} fields against {len(detected_placeholders)} target placeholders using deep manifest..."
                )
                formatted_data = await ai_service.harmonize_data_to_template_style(
                    structured_data=resume_data,
                    template_text=template_text_content,
                    detected_placeholders=detected_placeholders,
                    field_manifest=field_manifest,
                    formatting_guidance=formatting_guidance,
                    industry=state.get("industry") or "Professional Services",
                    summary_guidance=state.get("summary_guidance") or "",
                    job_id=session_id
                )


                resume_data.update(formatted_data)
                state["linearized_data"] = json.dumps(formatted_data, indent=2)


            # Normalize Keys for the Template Engine (Jinja2 / docxtpl)
            normalized_resume_data = {}
            for k, v in resume_data.items():
                # Map 'Professional Summary' or 'Summary' to 'summary' for consistency
                safe_key = k.lower().strip().replace(" ", "_").replace(":", "")
                normalized_resume_data[safe_key] = v
            
            # Ensure the specific 'summary' field is populated with our generated summary
            # but preserve both local 'summary' and the AI-generated 'summary_text'
            final_resume_data = {
                **normalized_resume_data,
                "summary": summary_text,
                "professional_summary": summary_text, # Aliased for common template designs
                "job_id": session_id,
            }

            # Log the final data mapping before document generation
            AuditService.log_event(
                job_id=session_id,
                event_type="DATA_BEFORE_DOC_GEN",
                payload={
                    **final_resume_data
                }
            )

            # Delegate rendering to dedicated generator service
            docx_bytes = generator_service.render_formatted_document(
                template_bytes=template_bytes,
                resume_data=final_resume_data,
                expected_fields=state.get("expected_fields") or "",
                field_extraction_manifest=state.get("field_extraction_manifest"),
            )

            render_key = f"jobs/{session_id}/output/formatted_resume.docx"
            render_docx_uri = storage.put_bytes(render_key, docx_bytes)

        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            # Fallback: Save an error document instead of crashing
            error_docx = generator_service.generate_error_docx(template_id, str(e))
            render_key = f"jobs/{session_id}/output/formatted_resume.docx"
            render_docx_uri = storage.put_bytes(render_key, error_docx)

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
