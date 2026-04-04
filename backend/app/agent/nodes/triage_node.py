import asyncio
from typing import Dict, Any, List

from app.agent.state import AgentState
from app.services.resume_ai_service import ResumeAiService
from app.services.hybrid_template_ranker import HybridTemplateRanker
from app.dependencies import get_knowledge_index
from app.db.session import SessionLocal
from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository

AUTO_TEMPLATE_SCORE_THRESHOLD = 0.85
NON_CANDIDATE_REJECT_THRESHOLD = 0.80

def create_triage_node(ai_service: ResumeAiService):
    async def triage_node(state: AgentState) -> dict:
        extracted_text = state.get("extracted_text", "")
        raw_parsed_data = state.get("raw_parsed_data") or {}
        extraction_confidence = state.get("extraction_confidence")
        filename = state.get("filename", "document.pdf")
        content_type = state.get("content_type", "application/pdf")
        selected_template_id = state.get("selected_template_id")
        runtime_metadata = state.get("runtime_metadata") or {}
        industry_id = runtime_metadata.get("industry_id")
        mode = state.get("intent", "recruiter_runtime")

        async def classify_task():
            return await ai_service.classify_document(
                extracted_text=extracted_text,
                raw_parsed_data=raw_parsed_data,
                filename=filename,
                content_type=content_type,
                extraction_confidence=extraction_confidence,
            )

        async def suggest_template_task():
            # If user already supplied a template, do not re-suggest here.
            if selected_template_id:
                return {
                    "top_template_id": selected_template_id,
                    "results": [],
                    "mode": "user_provided",
                }

            db = SessionLocal()
            try:
                repo = SqlAlchemyTemplateRepository(db)
                knowledge_index = get_knowledge_index()
                ranker = HybridTemplateRanker(knowledge_index, repo)

                # rank_templates should already restrict or be made to restrict ACTIVE templates.
                results = ranker.rank_templates(
                    extracted_text=extracted_text,
                    industry_id=industry_id,
                    mode=mode,
                ) or []

                return {
                    "top_template_id": results[0]["template_id"] if results else None,
                    "results": results[:3],
                    "mode": "suggested",
                }
            finally:
                db.close()

        classification, template_result = await asyncio.gather(
            classify_task(),
            suggest_template_task(),
        )

        document_kind = classification.get("document_kind", "ambiguous_candidate_document")
        document_confidence = float(classification.get("confidence", 0.5))
        document_reason = classification.get("reason", "")

        # Hard reject only for strong non-candidate classification
        if (
            document_kind == "non_candidate_document"
            and document_confidence >= NON_CANDIDATE_REJECT_THRESHOLD
        ):
            return {
                "document_kind": document_kind,
                "document_confidence": document_confidence,
                "document_reason": document_reason,
                "awaiting_confirmation": False,
                "status": "REJECTED_INVALID_DOCUMENT",
            }

        suggested_results = template_result.get("results", [])
        top_template_id = template_result.get("top_template_id")

        # User already provided template
        if selected_template_id:
            return {
                "document_kind": document_kind,
                "document_confidence": document_confidence,
                "document_reason": document_reason,
                "template_resolution_mode": "user_provided",
                "awaiting_confirmation": False,
                "status": "TRIAGE_READY",
            }

        # Auto-select if strong enough
        if suggested_results:
            top_score = float(suggested_results[0].get("score", 0.0))
            if top_template_id and top_score >= AUTO_TEMPLATE_SCORE_THRESHOLD:
                return {
                    "document_kind": document_kind,
                    "document_confidence": document_confidence,
                    "document_reason": document_reason,
                    "selected_template_id": top_template_id,
                    "suggested_template_id": top_template_id,
                    "suggested_template_ids": [r["template_id"] for r in suggested_results],
                    "suggested_template_scores": suggested_results,
                    "template_resolution_mode": "auto_selected",
                    "awaiting_confirmation": False,
                    "status": "TRIAGE_READY",
                }

        # Otherwise pause for confirmation
        return {
            "document_kind": document_kind,
            "document_confidence": document_confidence,
            "document_reason": document_reason,
            "suggested_template_id": top_template_id,
            "suggested_template_ids": [r["template_id"] for r in suggested_results],
            "suggested_template_scores": suggested_results,
            "template_resolution_mode": "needs_confirmation",
            "awaiting_confirmation": True,
            "status": "WAITING_FOR_CONFIRMATION",
        }

    return triage_node
