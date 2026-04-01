from langgraph.graph import StateGraph, END
from app.agent.state import AgentState

def build_workflow_graph() -> StateGraph:
    """
    Builds the bounded agentic workflow using LangGraph.

    The state starts at ingest and moves through document processing
    stages such as parse, normalize, apply privacy policies, resolve
    templates, validate constraints, and render output.
    """
    workflow = StateGraph(AgentState)

    # Define placeholder nodes for now
    workflow.add_node("ingest", lambda state: {"status": "ingested"})
    workflow.add_node("parse", lambda state: {"status": "parsed"})
    workflow.add_node("normalize", lambda state: {"status": "normalized"})
    workflow.add_node("privacy_transform", lambda state: {"status": "privacy_applied"})
    workflow.add_node("template_resolution", lambda state: {"status": "template_resolved"})
    workflow.add_node("transform", lambda state: {"status": "transformed"})
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
