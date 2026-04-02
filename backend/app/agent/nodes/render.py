from app.agent.state import AgentState
from app.adapters.base import LlmRuntimeAdapter
import json
import os
import tempfile
import io
from docxtpl import DocxTemplate

def create_render_node(llm_runtime: LlmRuntimeAdapter, storage):
    """
    Creates the LangGraph node for rendering the final outputs (resume summary and formatted CV).
    This node saves the artifacts to the StorageProvider and returns their URIs in the state.
    """
    def render_node(state: AgentState) -> dict:
        print("Executing Render Node...")

        transformed_json_str = state.get("transformed_document_json", "")
        session_id = state.get("session_id", "unknown-session")

        # Generate a summary
        # If there's no extracted data, fallback gracefully
        resume_data = {}
        summary_text = "Summary not available because document transformation did not produce valid data."

        try:
            if transformed_json_str:
                resume_data = json.loads(transformed_json_str)

                # Deterministic Fallback in case LLM fails
                skills = resume_data.get("skills", [])
                skills_str = ", ".join(skills[:5]) if skills else "various skills"
                experience = resume_data.get("experience", [])
                latest_role = experience[0].get("title", "professional") if experience else "professional"
                latest_company = experience[0].get("company", "recent companies") if experience else "recent companies"

                fallback_summary = f"A {latest_role} with experience at {latest_company}. Core expertise includes {skills_str}."

                # Try LLM for high-quality summary
                prompt = f"""
                Generate a concise recruiter-ready professional summary from the candidate's extracted resume data.
                Use only supplied facts. Exclude all PII (no names, emails, phones, addresses, or links).
                Do not invent missing details.
                Highlight role focus, core skills, domain exposure, responsibilities, and measurable achievements when explicitly supported.
                Return one paragraph of 90-140 words. Plain text only, no markdown bullets in the summary itself.

                Resume Data:
                {json.dumps(resume_data, indent=2)}
                """

                try:
                    summary_text = llm_runtime.generate(prompt=prompt, temperature=0.3).strip()
                    if not summary_text:
                        print("LLM returned empty summary, using fallback.")
                        summary_text = fallback_summary
                except Exception as llm_error:
                    print(f"Failed to generate summary via LLM: {llm_error}")
                    summary_text = fallback_summary

        except Exception as e:
            summary_text = "Summary generation failed."
            print(f"Failed to parse JSON for summary: {e}")

        # Save summary
        summary_key = f"jobs/{session_id}/output/summary.md"
        summary_uri = storage.put_bytes(summary_key, summary_text.encode("utf-8"))

        template_id = state.get("selected_template_id")
        render_docx_uri = None

        # We need to fetch the template from storage to render it.
        # Fallback to a basic template if we don't have it locally or if retrieval fails.
        try:
            template_key = f"templates/{template_id}/template.docx"
            template_bytes = storage.get_bytes(template_key)
            template_stream = io.BytesIO(template_bytes)
            doc = DocxTemplate(template_stream)
            doc.render(resume_data)

            out_stream = io.BytesIO()
            doc.save(out_stream)
            out_stream.seek(0)

            render_key = f"jobs/{session_id}/output/formatted_resume.docx"
            render_docx_uri = storage.put_bytes(render_key, out_stream.read())
        except Exception as e:
            print(f"Failed to load or render template {template_id} from storage: {e}")
            # If we couldn't render a real DOCX due to missing template, we can't save one.
            # In a real app we'd throw or use a baked-in default template.
            # Let's save a simple text fallback just to not break downstream if missing
            render_key = f"jobs/{session_id}/output/formatted_resume.txt"
            fallback_text = f"Failed to render docx due to missing template.\n\nData:\n{json.dumps(resume_data, indent=2)}"
            render_docx_uri = storage.put_bytes(render_key, fallback_text.encode("utf-8"))

        final_status = "rendered"
        # If transformation failed or was flagged, bubble that up to completed_with_warnings or needs_review
        if state.get("status") == "transformation_failed" or not state.get("validation_passed", True):
            final_status = "needs_review"

        return {
            "summary_uri": summary_uri,
            "render_docx_uri": render_docx_uri,
            "status": final_status
        }

    return render_node
