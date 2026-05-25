import asyncio
import logging
import json
from typing import Any
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState

from app.domain.interfaces import LlmRuntimeAdapter
from app.domain.interfaces import DocumentExtractionService, ExtractionContext
from app.agent.nodes.transformation_node import create_field_harmonization_node
from app.agent.nodes.agentic_nodes import create_template_contract_generation_node
from app.services.resume_parsing_service import ResumeParsingService
from app.dependencies import get_storage_provider

logger = logging.getLogger(__name__)


def create_validity_check_node():
    async def validity_node(state: AgentState):
        text = state.get("extracted_text", "")
        is_resume = "experience" in text.lower() or "education" in text.lower()
        if not is_resume and len(text) > 0:
            return {"status": "rejected_not_resume"}
        return {"status": "valid_resume"}
    return validity_node


def create_parse_node(doc_parser: DocumentExtractionService, storage):
    async def parse_node(state: AgentState):
        file_path = state.get("file_path")
        intent = state.get("intent", "candidate_runtime")
        actor_role = state.get("actor_role", "system")
        filename = state.get("filename", "unknown.pdf")
        content_type = state.get("content_type", "application/pdf")

        context = ExtractionContext(intent=intent, actor_role=actor_role)

        try:
            file_bytes = storage.get_bytes(file_path)
        except Exception as e:
            logger.error(f"Failed to fetch file from storage: {file_path}. Error: {e}")
            file_bytes = b""

        parsing_service = ResumeParsingService(extractor=doc_parser)
        result = await parsing_service.ingest(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            context=context,
        )

        extracted_text = result.get("extracted_text", "")
        logger.info(f"Parsed document: {filename}, length: {len(extracted_text)} chars")

        return {
            "extracted_text": extracted_text,
            "raw_parsed_data": result.get("structured_data", {}),
            "extraction_confidence": 0.95,
            "status": result.get("status", "parsed"),
        }
    return parse_node


def with_progress(node_name, node_func, stage_map, job_repo, status_map=None):
    async def wrapped_node(state: AgentState):
        job_id = state.get("session_id")
        if job_repo and job_id:
            try:
                job = job_repo.get_job(job_id)
                if job:
                    job.stage = stage_map.get(node_name, node_name)
                    if status_map and node_name in status_map:
                        job.status = status_map[node_name]
                    if state.get("template_asset_id"):
                        job.template_asset_id = state.get("template_asset_id")
                    if state.get("transformed_document_json"):
                        transformed_data = state["transformed_document_json"]
                        if isinstance(transformed_data, dict):
                            if "filled_template_manifest" in transformed_data:
                                job.transformed_json = json.dumps(transformed_data["filled_template_manifest"])
                            else:
                                job.transformed_json = json.dumps(transformed_data)
                        else:
                            job.transformed_json = str(transformed_data)
                    if state.get("raw_parsed_data"):
                        job.candidate_facts_json = (
                            json.dumps(state["raw_parsed_data"])
                            if isinstance(state["raw_parsed_data"], dict)
                            else str(state["raw_parsed_data"])
                        )
                    job_repo.save_job(job)
            except Exception as e:
                logger.warning(f"Non-critical: Failed to update job progress: {e}")

        if hasattr(node_func, "ainvoke"):
            return await node_func.ainvoke(state)
        if asyncio.iscoroutinefunction(node_func):
            return await node_func(state)
        return node_func(state)
    return wrapped_node


def build_template_processing_graph(
    doc_parser: DocumentExtractionService, storage=None, job_repo=None
) -> Any:
    """Graph for template processing (admin upload path)."""
    workflow = StateGraph(AgentState)
    if storage is None:
        storage = get_storage_provider()

    stage_map = {
        "ingest": "ingest",
        "parse_template_docx": "parse",
        "generate_contract": "generate_contract",
        "store_contract": "store_contract",
    }

    workflow.add_node("ingest", with_progress("ingest", lambda state: {"status": "ingested"}, stage_map, job_repo))
    workflow.add_node("parse_template_docx", with_progress("parse_template_docx", create_parse_node(doc_parser, storage), stage_map, job_repo))
    workflow.add_node("generate_contract", with_progress("generate_contract", create_template_contract_generation_node(), stage_map, job_repo))
    workflow.add_node("store_contract", with_progress("store_contract", lambda state: {"status": "contract_stored"}, stage_map, job_repo))

    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "parse_template_docx")
    workflow.add_edge("parse_template_docx", "generate_contract")
    workflow.add_edge("generate_contract", "store_contract")
    workflow.add_edge("store_contract", END)

    return workflow.compile()


def build_resume_processing_graph(
    llm_runtime: LlmRuntimeAdapter,
    doc_parser: DocumentExtractionService,
    storage=None,
    job_repo=None,
) -> Any:
    """
    Simplified candidate resume processing graph.

    Pipeline (2 LLM calls total):
        load_template         – template analysis LLM call (existing)
        extract_resume_facts  – parse PDF/DOCX (no LLM)
        validate_resume       – heuristic guard (no LLM)
        generate_cv_summary   – short summary LLM call (for cv_comments field)
        map_facts_to_manifest – 1 LLM call → enriched manifest;
                                Python derives template_fill_result deterministically
        composition           – render DOCX (no LLM)
    """
    workflow = StateGraph(AgentState)
    if storage is None:
        storage = get_storage_provider()

    from app.schemas.enums import JobStatus
    from app.services.resume_ai_service import ResumeAiService
    from app.services.resume_generator_service import ResumeGeneratorService
    from app.agent.nodes.template_resolution_node import create_template_resolve_node
    from app.agent.nodes.formatter_resume_node import create_document_composition_node
    from app.agent.nodes.agentic_nodes import create_summary_generation_node

    ai_service = ResumeAiService(llm_runtime, doc_parser)
    generator_service = ResumeGeneratorService()

    stage_map = {
        "load_template":         "LOADING_TEMPLATE",
        "extract_resume_facts":  "EXTRACTING_FACTS",
        "validate_resume":       "EXTRACTING_FACTS",
        "generate_cv_summary":   "GENERATING_SUMMARY",
        "map_facts_to_manifest": "MAPPING_FIELDS",
        "composition":           "RENDERING_DOCX",
    }

    status_map = {
        "load_template":         JobStatus.PROCESSING,
        "extract_resume_facts":  JobStatus.PROCESSING,
        "generate_cv_summary":   JobStatus.SUMMARIZING,
        "map_facts_to_manifest": JobStatus.MAPPING,
        "composition":           JobStatus.PROCESSING,
    }

    # 1. Load Template
    workflow.add_node("load_template", with_progress(
        "load_template",
        create_template_resolve_node(llm_runtime, storage, doc_parser),
        stage_map, job_repo, status_map,
    ))

    # 2. Extract Resume Facts
    workflow.add_node("extract_resume_facts", with_progress(
        "extract_resume_facts",
        create_parse_node(doc_parser, storage),
        stage_map, job_repo, status_map,
    ))

    # 2b. Validate Resume
    workflow.add_node("validate_resume", with_progress(
        "validate_resume",
        create_validity_check_node(),
        stage_map, job_repo, status_map,
    ))

    # 3. Generate CV Summary (LLM call for summary / cv_comments field)
    workflow.add_node("generate_cv_summary", with_progress(
        "generate_cv_summary",
        create_summary_generation_node(ai_service, storage),
        stage_map, job_repo, status_map,
    ))

    # 4. Map Facts → Manifest (1 LLM call; Python derives template_fill_result)
    workflow.add_node("map_facts_to_manifest", with_progress(
        "map_facts_to_manifest",
        create_field_harmonization_node(ai_service),
        stage_map, job_repo, status_map,
    ))

    # 5. Composition: render DOCX (no LLM)
    workflow.add_node("composition", with_progress(
        "composition",
        create_document_composition_node(ai_service, generator_service, storage),
        stage_map, job_repo, status_map,
    ))

    workflow.set_entry_point("load_template")
    workflow.add_edge("load_template",         "extract_resume_facts")
    workflow.add_edge("extract_resume_facts",   "validate_resume")
    workflow.add_edge("validate_resume",         "generate_cv_summary")
    workflow.add_edge("generate_cv_summary",     "map_facts_to_manifest")
    workflow.add_edge("map_facts_to_manifest",   "composition")
    workflow.add_edge("composition",             END)

    return workflow.compile()
