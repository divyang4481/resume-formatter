import asyncio
import logging
from typing import Dict, Any, List

from app.agent.state import AgentState
from app.services.resume_ai_service import ResumeAiService
from app.services.hybrid_template_ranker import HybridTemplateRanker
from app.dependencies import get_knowledge_index
from app.db.session import SessionLocal
from app.adapters.repositories.template_repository import SqlAlchemyTemplateRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

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
            nonlocal selected_template_id
            db = SessionLocal()
            try:
                # 1. FINAL RECOVERY: If selected_template_id is missing from state, 
                # check the DB directly one last time to avoid desync.
                if not selected_template_id:
                    from app.db.models import ProcessingJob
                    job_record = db.query(ProcessingJob).filter(ProcessingJob.id == state.get("session_id")).first()
                    if job_record:
                        # Use the correct DB column name 'template_asset_id'
                        db_template_id = getattr(job_record, 'template_asset_id', None)
                        if db_template_id:
                            selected_template_id = db_template_id
                            logger.info(f"Triage Node: Recovered selected_template_id '{selected_template_id}' from DB column 'template_asset_id'.")

                # 2. SHORT-CIRCUIT: If we have a target template, skip the guessing game.
                if selected_template_id:
                    return {
                        "top_template_id": selected_template_id,
                        "results": [],
                        "mode": "user_provided",
                    }

                # 3. RANKING: Only guess if we truly have no starting template
                repo = SqlAlchemyTemplateRepository(db)
                knowledge_index = get_knowledge_index()
                ranker = HybridTemplateRanker(knowledge_index, repo)

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

        # User already provided template (or recovered from DB)
        if selected_template_id:
            AuditService.log_event(
                job_id=state.get("session_id"),
                event_type="TEMPLATE_PROVIDED_IN_SUBMIT",
                payload={"template_id": selected_template_id}
            )
            return {
                "document_kind": document_kind,
                "document_confidence": document_confidence,
                "document_reason": document_reason,
                "selected_template_id": selected_template_id,
                "template_resolution_mode": "user_provided",
                "awaiting_confirmation": False,
                "status": "TRIAGE_READY",
            }

        # Auto-select if strong enough
        if suggested_results:
            top_score = float(suggested_results[0].get("score", 0.0))
            if top_template_id and top_score >= AUTO_TEMPLATE_SCORE_THRESHOLD:
                AuditService.log_event(
                    job_id=state.get("session_id"),
                    event_type="TEMPLATE_SUGGESTED_AND_SELECTED",
                    payload={
                        "template_id": top_template_id,
                        "score": top_score,
                        "suggested_results": suggested_results
                    }
                )
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
