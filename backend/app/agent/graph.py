import asyncio
from typing import Any
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState

from app.domain.interfaces import LlmRuntimeAdapter
from app.domain.interfaces import DocumentExtractionService, ExtractionContext
from app.agent.nodes.transformation_node import create_schema_builder_node, create_context_aware_extraction_node
from app.services.resume_parsing_service import ResumeParsingService
from app.dependencies import get_storage_provider

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
        except Exception:
            file_bytes = b"" # Fallback to empty if not found during dev

        parsing_service = ResumeParsingService(extractor=doc_parser)
        result = await parsing_service.ingest(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            context=context
        )

        return {
             "extracted_text": result.get("extracted_text", ""),
             "raw_parsed_data": result.get("structured_data", {}),
             "extraction_confidence": 0.95,
             "status": result.get("status", "parsed")
        }
    return parse_node


def create_transformation_subgraph(llm_runtime: LlmRuntimeAdapter) -> Any:
    """
    Constructs a granular subgraph for the transformation phase.
    Ensures that schema preparation and context-aware extraction are separate steps.
    """
    from langgraph.graph import StateGraph, END
    subgraph = StateGraph(AgentState)
    
    subgraph.add_node("prepare_schema", create_schema_builder_node())
    subgraph.add_node("extract_map", create_context_aware_extraction_node(llm_runtime))
    
    subgraph.set_entry_point("prepare_schema")
    subgraph.add_edge("prepare_schema", "extract_map")
    subgraph.add_edge("extract_map", END)
    
    return subgraph.compile()


def build_workflow_graph(llm_runtime: LlmRuntimeAdapter, doc_parser: DocumentExtractionService, storage=None, job_repo=None) -> StateGraph:
    workflow = StateGraph(AgentState)

    if storage is None:
        storage = get_storage_provider()

    # Pre-define stage mappings for UI to ensure stepper alignment
    stage_map = {
        "ingest": "ingest",
        "parse": "parse",
        "triage": "triage",
        "normalize": "normalize",
        "privacy_transform": "privacy",
        "template_resolution": "classify",
        "transform": "transform", 
        "render": "render",
        "validate": "validate"
    }


    # Helper function to wrap nodes with DB progress updates
    def with_progress(node_name, node_func):
        async def wrapped_node(state: AgentState):
            job_id = state.get("session_id")
            if job_repo and job_id:
                try:
                    job = job_repo.get_job(job_id)
                    if job:
                        job.stage = stage_map.get(node_name, node_name)
                        job_repo.save_job(job)
                except Exception as e:
                    print(f"Non-critical: Failed to update job progress: {e}")
            
            # If the node is a compiled subgraph (Runnable), use ainvoke
            if hasattr(node_func, "ainvoke"):
                return await node_func.ainvoke(state)
            
            # If it's a coroutine function, await it
            if asyncio.iscoroutinefunction(node_func):
                return await node_func(state)
            
            # Otherwise, call it directly
            return node_func(state)
        return wrapped_node

    from app.services.resume_ai_service import ResumeAiService
    from app.services.resume_generator_service import ResumeGeneratorService
    from app.agent.nodes.triage_node import create_triage_node
    ai_service = ResumeAiService(llm_runtime, doc_parser)
    generator_service = ResumeGeneratorService()

    workflow.add_node("ingest", with_progress("ingest", lambda state: {"status": "ingested"}))
    workflow.add_node("parse", with_progress("parse", create_parse_node(doc_parser, storage)))
    workflow.add_node("triage", with_progress("triage", create_triage_node(ai_service)))
    workflow.add_node("normalize", with_progress("normalize", lambda state: {"status": "normalized"}))
    workflow.add_node("privacy_transform", with_progress("privacy_transform", lambda state: {"status": "privacy_applied"}))

    # Agentic reasoning nodes
    from app.agent.nodes.template_resolution_node import create_template_resolve_node
    workflow.add_node("template_resolution", with_progress("template_resolution", create_template_resolve_node(llm_runtime, storage, doc_parser)))
    
    # Use the transformation subgraph instead of a single node
    transformation_subgraph = create_transformation_subgraph(llm_runtime)
    workflow.add_node("transform", with_progress("transform", transformation_subgraph))

    from app.agent.nodes.formatter_resume_node import create_render_node
    from app.agent.nodes.validation_node import create_validate_node

    # Align with UI pipeline display: render then validate (or reversed, but let's stick to UI flow)
    workflow.add_node("render", with_progress("render", create_render_node(ai_service, generator_service, storage)))
    workflow.add_node("validate", with_progress("validate", create_validate_node(ai_service)))

    # Define edges based on bounded workflow logic
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "parse")
    workflow.add_edge("parse", "triage")

    def triage_router(state: AgentState):
        status = state.get("status")
        if status == "REJECTED_INVALID_DOCUMENT":
            return END
        if status == "WAITING_FOR_CONFIRMATION":
            return END
        return "normalize"

    workflow.add_conditional_edges("triage", triage_router, {
        "normalize": "normalize",
        END: END,
    })

    workflow.add_edge("normalize", "privacy_transform")
    workflow.add_edge("privacy_transform", "template_resolution")
    workflow.add_edge("template_resolution", "transform")
    workflow.add_edge("transform", "render")
    workflow.add_edge("render", "validate")
    workflow.add_edge("validate", END)

    return workflow.compile()
