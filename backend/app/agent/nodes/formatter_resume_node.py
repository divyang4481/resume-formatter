import json
import logging
import io

from app.agent.state import AgentState
from app.services.resume_ai_service import ResumeAiService
from app.services.resume_generator_service import ResumeGeneratorService
from app.services.template_render_planner import TemplateRenderPlanner
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


def create_render_node(
    ai_service: ResumeAiService,
    generator_service: ResumeGeneratorService,
    storage,
):
    """
    LangGraph node for the Document Rendering stage.

    Flow
    ----
    1. Parse transformed JSON from state (structured, NOT flattened)
    2. Ask TemplateRenderPlanner for per-section render instructions
    3. ResumeGeneratorService uses SectionRenderEngine (AI for scalars,
       SchemaInference for structured sections) per field using manifest
    4. Save artefacts and return updated state
    """
    # Build a generator that has the LLM wired in for per-field AI polish
    from app.services.resume_generator_service import ResumeGeneratorService as _Gen
    llm_aware_generator = _Gen(llm=ai_service.llm)
    planner = TemplateRenderPlanner()

    async def render_node(state: AgentState) -> dict:
        session_id = state.get("session_id", "unknown-session")
        logger.info(f"Executing Render Node (session={session_id})...")

        # ── 1. Parse structured data ───────────────────────────────────────
        resume_data: dict = {}
        transformed_json_str = state.get("transformed_document_json", "")
        try:
            if transformed_json_str:
                from app.agent.utils.llm_sanitizer import LlmSanitizer
                cleaned = LlmSanitizer.clean_json(transformed_json_str)
                resume_data = json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to parse transformed JSON: {e}")

        # ── 2. Summary artefact ────────────────────────────────────────────
        summary_text = state.get("overall_resume_summary") or "Summary not available."
        summary_key = f"jobs/{session_id}/output/summary.md"
        summary_md  = f"### CV Summary\n\n{summary_text}"
        summary_uri = storage.put_bytes(summary_key, summary_md.encode("utf-8"))

        # ── 3. Resolve template ────────────────────────────────────────────
        template_id          = state.get("selected_template_id") or "general_cv_v1"
        template_storage_uri = state.get("template_storage_uri")
        render_docx_uri      = None

        try:
            template_key = (
                template_storage_uri.replace("local://", "")
                if template_storage_uri
                else f"templates/{template_id}/template.docx"
            )
            logger.info(f"Loading template from storage key: {template_key}")
            template_bytes = storage.get_bytes(template_key)

            # ── 4. Build render plan ───────────────────────────────────────
            expected_fields_raw = state.get("expected_fields") or ""
            expected_fields_list = [
                f.strip() for f in expected_fields_raw.split(",") if f.strip()
            ]
            field_manifest = state.get("field_extraction_manifest") or []

            render_plan = planner.build_plan(
                expected_fields=expected_fields_list,
                field_manifest=field_manifest if isinstance(field_manifest, list) else [],
                resume_data=resume_data,
            )

            # Store plan in state for diagnostics / validation node
            state["render_plan"] = render_plan

            # Debug diagnostics — not authoritative render source
            state["linearized_data"] = json.dumps(
                {p["fieldname"]: p["render_mode"] for p in render_plan}, indent=2
            )

            logger.info(
                f"Render plan: {len(render_plan)} fields | "
                f"modes={list({p['render_mode'] for p in render_plan})}"
            )

            AuditService.log_event(
                job_id=session_id,
                event_type="RENDER_PLAN_BUILT",
                payload={"render_plan_summary": [
                    {"fieldname": p["fieldname"], "render_mode": p["render_mode"]}
                    for p in render_plan
                ]},
            )

            # ── 5. Resolve manifest fieldnames → extracted data values ─────
            # Bridges the gap between manifest keys (e.g. 'professional_summary')
            # and extraction output keys (e.g. 'summary', 'experience')
            manifest_list = field_manifest if isinstance(field_manifest, list) else []
            resolved_resume_data = planner.resolve_data(
                field_manifest=manifest_list,
                resume_data=resume_data,
                summary_text=summary_text,
            )
            resolved_resume_data["job_id"] = session_id

            AuditService.log_event(
                job_id=session_id,
                event_type="DATA_BEFORE_DOC_GEN",
                payload={
                    "resolved_keys": list(resolved_resume_data.keys()),
                    "manifest_fields_resolved": [
                        {"field": m.get("fieldname"), "has_value": bool(resolved_resume_data.get(m.get("fieldname", "")))}
                        for m in manifest_list if isinstance(m, dict)
                    ]
                },
            )

            # ── 6. Delegate to LLM-aware ResumeGeneratorService ─────────────
            docx_bytes, linearized_data = llm_aware_generator.render_formatted_document(
                template_bytes=template_bytes,
                resume_data=resolved_resume_data,
                expected_fields=expected_fields_raw,
                field_extraction_manifest=field_manifest,
                job_id=session_id,
            )

            state["linearized_data"] = linearized_data
            render_key     = f"jobs/{session_id}/output/formatted_resume.docx"
            render_docx_uri = storage.put_bytes(render_key, docx_bytes)
            logger.info(f"DOCX rendered successfully → {render_key}")

        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            error_docx = llm_aware_generator.generate_error_docx(template_id, str(e))
            render_key     = f"jobs/{session_id}/output/formatted_resume.docx"
            render_docx_uri = storage.put_bytes(render_key, error_docx)
            linearized_data = json.dumps({"error": str(e)})

        # ── 7. Final state ─────────────────────────────────────────────────
        from app.agent.utils.llm_sanitizer import LlmSanitizer
        clean_summary = LlmSanitizer.strip_cvml(summary_text)

        final_status = "rendered" if state.get("validation_passed", True) else "needs_review"

        return {
            "summary_text":    clean_summary,
            "summary_uri":     summary_uri,
            "render_docx_uri": render_docx_uri,
            "linearized_data": linearized_data,
            "status":          final_status,
        }

    return render_node
