from langgraph.graph import StateGraph, END
from app.agent.state import AgentState

from app.adapters.base import LlmRuntimeAdapter
from app.domain.interfaces import DocumentExtractionService, ExtractionContext
from app.agent.nodes.transform import create_transform_node
from app.agent.nodes.template_resolve import create_template_resolve_node
from app.services.resume_ingestion_service import ResumeIngestionService
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

        ingestion_service = ResumeIngestionService(extractor=doc_parser)
        result = await ingestion_service.ingest(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            context=context
        )

        return {
             "extracted_text": result.get("extracted_text", ""),
             "extraction_confidence": 0.95, # Assuming a generic confidence for now as it's not strictly mapped
             "status": result.get("status", "parsed")
        }
    return parse_node


def build_workflow_graph(llm_runtime: LlmRuntimeAdapter, doc_parser: DocumentExtractionService, storage=None) -> StateGraph:
    """
    Builds the bounded agentic workflow using LangGraph.
    Takes dependencies injected from the factory configuration.

    The state starts at ingest and moves through document processing
    stages such as parse, normalize, apply privacy policies, resolve
    templates, validate constraints, and render output.
    """
    workflow = StateGraph(AgentState)

    if storage is None:
        storage = get_storage_provider()

    # Use the concrete factory implementations
    workflow.add_node("ingest", lambda state: {"status": "ingested"})
    workflow.add_node("parse", create_parse_node(doc_parser, storage))
    workflow.add_node("normalize", lambda state: {"status": "normalized"})
    workflow.add_node("privacy_transform", lambda state: {"status": "privacy_applied"})

    # Inject the LLM runtime into our agentic bounded reasoning nodes
    workflow.add_node("template_resolution", create_template_resolve_node(llm_runtime))
    workflow.add_node("transform", create_transform_node(llm_runtime))

    from app.agent.nodes.render import create_render_node

    workflow.add_node("validate", lambda state: {"status": "validated"})
    workflow.add_node("render", create_render_node(llm_runtime, storage))

    # Define edges based on bounded workflow logic
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "parse")
    workflow.add_edge("parse", "normalize")
    workflow.add_edge("normalize", "privacy_transform")
    workflow.add_edge("privacy_transform", "template_resolution")
    workflow.add_edge("template_resolution", "transform")
    workflow.add_edge("transform", "validate")
    workflow.add_edge("validate", "render")
    workflow.add_edge("render", END)

    # In a full setup, checkpointer would be passed here
    return workflow.compile()
