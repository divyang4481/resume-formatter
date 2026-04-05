from app.agent.state import AgentState
from app.services.resume_ai_service import ResumeAiService
from app.services.audit_service import AuditService
import logging

logger = logging.getLogger(__name__)

def create_resume_summarizer_node(ai_service: ResumeAiService):
    """
    Creates a node that generates an overall, pure-text resume summary.
    This is separate from any summary field inside the resume template.
    """
    async def summarize_node(state: AgentState) -> dict:
        session_id = state.get("session_id", "unknown-session")
        extracted_text = state.get("extracted_text", "")
        summary_guidance = state.get("summary_guidance") or ""
        industry = state.get("industry")
        template_id = state.get("selected_template_id")
        template_text = state.get("template_text")
        language = state.get("language", "en")

        logger.info(f"Generating Overall Resume Summary for session {session_id}...")

        if not extracted_text:
            logger.warning("No extracted text found for summary generation.")
            return {"overall_resume_summary": "Original resume text not found. Summary cannot be generated."}

        try:
            # Use AI Service for overall pure-text summary
            overall_summary = await ai_service.generate_overall_summary(
                extracted_text=extracted_text,
                guidance=summary_guidance,
                industry=industry,
                template_id=template_id,
                template_text=template_text,
                language=language,
                job_id=session_id
            )
            
            return {
                "overall_resume_summary": overall_summary,
                "status": "summarized"
            }
        except Exception as e:
            logger.error(f"Overall summary generation error: {e}")
            return {
                "overall_resume_summary": "Summary generation failed.",
                "status": "summary_failed"
            }

    return summarize_node
