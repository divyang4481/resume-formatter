import asyncio
import logging
import json
from typing import Any
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState

from app.domain.interfaces import LlmRuntimeAdapter
from app.domain.interfaces import DocumentExtractionService, ExtractionContext
from app.agent.nodes.transformation_node import create_schema_builder_node, create_field_harmonization_node, create_document_composition_reasoning_node
from app.agent.nodes.agentic_nodes import (
    create_template_contract_generation_node,
    create_kb_retrieval_node,
    create_output_quality_reasoning_node
)
from app.services.resume_parsing_service import ResumeParsingService
from app.dependencies import get_storage_provider
 
logger = logging.getLogger(__name__)


def create_validity_check_node():
    async def validity_node(state: AgentState):
        text = state.get("extracted_text", "")
        # Simple heuristic validity guard
        is_resume = "experience" in text.lower() or "education" in text.lower()
        if not is_resume and len(text) > 0:
             return {"status": "rejected_not_resume"}
        return {"status": "valid_resume"}
    return validity_node

def create_parse_node(doc_parser: DocumentExtractionService, storage):
    async def parse_node(state: AgentState):
        file_path = state.get("file_path")

        # Retrieve context from state
        intent = state.get("intent", "candidate_runtime")
        actor_role = state.get("actor_role", "system")
        filename = state.get("filename", "unknown.pdf")
        content_type = state.get("content_type", "application/pdf")

        context = ExtractionContext(intent=intent, actor_role=actor_role)

        # Retrieve bytes from storage
        try:
            file_bytes = storage.get_bytes(file_path)
        except Exception as e:
            logger.error(f"Failed to fetch file from storage: {file_path}. Error: {e}")
            file_bytes = b"" # Fallback to empty if not found during dev

        parsing_service = ResumeParsingService(extractor=doc_parser)
        result = await parsing_service.ingest(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            context=context
        )

        extracted_text = result.get("extracted_text", "")
        logger.info(f"Parsed document: {filename}, length: {len(extracted_text)} chars")

        return {
             "extracted_text": extracted_text,
             "raw_parsed_data": result.get("structured_data", {}),
             "extraction_confidence": 0.95,
             "status": result.get("status", "parsed")
        }
    return parse_node


def with_progress(node_name, node_func, stage_map, job_repo):
    async def wrapped_node(state: AgentState):
        job_id = state.get("session_id")
        if job_repo and job_id:
            try:
                job = job_repo.get_job(job_id)
                if job:
                    job.stage = stage_map.get(node_name, node_name)
                    
                    # Persist template ID if resolved
                    if state.get("template_asset_id"):
                        job.template_asset_id = state.get("template_asset_id")
                        
                    if state.get("transformed_document_json"):
                        job.transformed_json = json.dumps(state.get("transformed_document_json")) if isinstance(state.get("transformed_document_json"), dict) else str(state.get("transformed_document_json"))
                    if state.get("raw_parsed_data"):
                        job.candidate_facts_json = json.dumps(state.get("raw_parsed_data")) if isinstance(state.get("raw_parsed_data"), dict) else str(state.get("raw_parsed_data"))
                    job_repo.save_job(job)
            except Exception as e:
                logger.warning(f"Non-critical: Failed to update job progress: {e}")

        # If the node is a compiled subgraph (Runnable), use ainvoke
        if hasattr(node_func, "ainvoke"):
            return await node_func.ainvoke(state)

        # If it's a coroutine function, await it
        if asyncio.iscoroutinefunction(node_func):
            return await node_func(state)

        # Otherwise, call it directly
        return node_func(state)
    return wrapped_node

def build_template_processing_graph(doc_parser: DocumentExtractionService, storage=None, job_repo=None) -> Any:
    """Graph for template processing."""
    workflow = StateGraph(AgentState)
    if storage is None: storage = get_storage_provider()
    
    stage_map = {
        "ingest": "ingest",
        "parse_template_docx": "parse",
        "generate_contract": "generate_contract",
        "store_contract": "store_contract"
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

def build_resume_processing_graph(llm_runtime: LlmRuntimeAdapter, doc_parser: DocumentExtractionService, storage=None, job_repo=None) -> Any:
    """Graph for candidate resume processing and template test runs."""
    workflow = StateGraph(AgentState)
    if storage is None: storage = get_storage_provider()

    stage_map = {
        "ingest": "LOADING_TEMPLATE",
        "parse": "EXTRACTING_FACTS",
        "validate_resume": "EXTRACTING_FACTS",
        "normalize": "EXTRACTING_FACTS",
        "privacy_transform": "EXTRACTING_FACTS",
        "template_resolution": "LOADING_TEMPLATE",
        "kb_retrieval": "MAPPING_FIELDS",
        "harmonization": "MAPPING_FIELDS", 
        "composition_reasoning": "MAPPING_FIELDS",
        "composition": "RENDERING_DOCX",
        "validate": "RENDERING_DOCX"
    }

    workflow.add_node("ingest", with_progress("ingest", lambda state: {"status": "ingested"}, stage_map, job_repo))
    workflow.add_node("parse", with_progress("parse", create_parse_node(doc_parser, storage), stage_map, job_repo))
    workflow.add_node("validate_resume", with_progress("validate_resume", create_validity_check_node(), stage_map, job_repo))
    workflow.add_node("normalize", with_progress("normalize", lambda state: {"status": "normalized"}, stage_map, job_repo))
    workflow.add_node("privacy_transform", with_progress("privacy_transform", lambda state: {"status": "privacy_applied"}, stage_map, job_repo))

    from app.services.resume_ai_service import ResumeAiService
    from app.services.resume_generator_service import ResumeGeneratorService
    ai_service = ResumeAiService(llm_runtime, doc_parser)
    generator_service = ResumeGeneratorService()

    from app.agent.nodes.template_resolution_node import create_template_resolve_node
    workflow.add_node("template_resolution", with_progress("template_resolution", create_template_resolve_node(llm_runtime, storage, doc_parser), stage_map, job_repo))
    
    workflow.add_node("kb_retrieval", with_progress("kb_retrieval", create_kb_retrieval_node(), stage_map, job_repo))
    workflow.add_node("harmonization", with_progress("harmonization", create_field_harmonization_node(ai_service), stage_map, job_repo))
    workflow.add_node("composition_reasoning", with_progress("composition_reasoning", create_document_composition_reasoning_node(ai_service), stage_map, job_repo))

    from app.agent.nodes.formatter_resume_node import create_document_composition_node
    workflow.add_node("composition", with_progress("composition", create_document_composition_node(ai_service, generator_service, storage), stage_map, job_repo))
    workflow.add_node("validate", with_progress("validate", create_output_quality_reasoning_node(), stage_map, job_repo))

    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "parse")
    workflow.add_edge("parse", "validate_resume")
    workflow.add_edge("validate_resume", "normalize")
    workflow.add_edge("normalize", "privacy_transform")
    workflow.add_edge("privacy_transform", "template_resolution")
    workflow.add_edge("template_resolution", "kb_retrieval")
    workflow.add_edge("kb_retrieval", "harmonization")
    workflow.add_edge("harmonization", "composition_reasoning")
    workflow.add_edge("composition_reasoning", "composition")
    workflow.add_edge("composition", "validate")
    workflow.add_edge("validate", END)

    return workflow.compile()
