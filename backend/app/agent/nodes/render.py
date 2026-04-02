from app.agent.state import AgentState
from app.adapters.base import LlmRuntimeAdapter
import json

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
        try:
            if transformed_json_str:
                resume_data = json.loads(transformed_json_str)
                name = resume_data.get("personal_info", {}).get("name", "Candidate")
                skills = resume_data.get("skills", [])
                skills_str = ", ".join(skills[:5]) if skills else "various skills"
                summary_text = f"**{name}** is a strong candidate with expertise in {skills_str}. This CV has been processed and PII-redacted."
            else:
                summary_text = "Summary not available because document transformation did not produce valid data."
        except Exception as e:
            summary_text = "Summary generation failed."
            print(f"Failed to generate summary: {e}")

        # In a real app, you would use a templating engine (like docxxtpl) and a PDF converter.
        # For this prototype, we'll create a basic markdown document to represent the DOCX/PDF content
        # and store it.

        docx_mock_content = f"""# Formatted Resume

(This is a generated DOCX mock)

{transformed_json_str}
"""

        # Save summary
        summary_key = f"jobs/{session_id}/output/summary.md"
        summary_uri = storage.put_bytes(summary_key, summary_text.encode("utf-8"))

        # Save "DOCX" output
        render_key = f"jobs/{session_id}/output/formatted_resume.md"
        render_uri = storage.put_bytes(render_key, docx_mock_content.encode("utf-8"))

        return {
            "summary_uri": summary_uri,
            "render_uri": render_uri,
            "status": "rendered"
        }

    return render_node
