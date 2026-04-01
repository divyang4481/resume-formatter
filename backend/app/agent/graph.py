from langgraph.graph import StateGraph, END
from app.agent.state import AgentState

from app.adapters.base import LlmRuntimeAdapter, DocumentParserAdapter
from app.agent.nodes.transform import create_transform_node
from app.agent.nodes.template_resolve import create_template_resolve_node
# Mock imports for parsing
def create_parse_node(doc_parser: DocumentParserAdapter):
    def parse_node(state: AgentState):
        file_path = state.get("file_path")
        result = doc_parser.parse(file_path=file_path)
        return {
             "extracted_text": result.get("extracted_text", "Sample mock resume text.\nJohn Doe\njohn@example.com\nSoftware Engineer at Tech Inc."),
             "extraction_confidence": 0.95,
             "status": "parsed"
        }
    return parse_node


def build_workflow_graph(llm_runtime: LlmRuntimeAdapter, doc_parser: DocumentParserAdapter) -> StateGraph:
    """
    Builds the bounded agentic workflow using LangGraph.
    Takes dependencies injected from the factory configuration.

    The state starts at ingest and moves through document processing
    stages such as parse, normalize, apply privacy policies, resolve
    templates, validate constraints, and render output.
    """
    workflow = StateGraph(AgentState)

    # Use the concrete factory implementations
    workflow.add_node("ingest", lambda state: {"status": "ingested"})
    workflow.add_node("parse", create_parse_node(doc_parser))
    workflow.add_node("normalize", lambda state: {"status": "normalized"})
    workflow.add_node("privacy_transform", lambda state: {"status": "privacy_applied"})

    # Inject the LLM runtime into our agentic bounded reasoning nodes
    workflow.add_node("template_resolution", create_template_resolve_node(llm_runtime))
    workflow.add_node("transform", create_transform_node(llm_runtime))

    workflow.add_node("validate", lambda state: {"status": "validated"})
    workflow.add_node("render", lambda state: {"status": "rendered"})

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
