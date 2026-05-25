def update_graph():
    with open('backend/app/agent/graph.py', 'r') as f:
        content = f.read()

    # Remove create_schema_builder_node from imports
    content = content.replace("from app.agent.nodes.transformation_node import create_schema_builder_node, create_context_aware_extraction_node", "from app.agent.nodes.transformation_node import create_context_aware_extraction_node")

    old_subgraph = """def create_transformation_subgraph(llm_runtime: LlmRuntimeAdapter) -> Any:
    \"\"\"
    Constructs a granular subgraph for the transformation phase.
    Ensures that schema preparation and context-aware extraction are separate steps.
    \"\"\"
    from langgraph.graph import StateGraph, END
    subgraph = StateGraph(AgentState)

    subgraph.add_node("prepare_schema", create_schema_builder_node())
    subgraph.add_node("extract_map", create_context_aware_extraction_node(llm_runtime))

    subgraph.set_entry_point("prepare_schema")
    subgraph.add_edge("prepare_schema", "extract_map")
    subgraph.add_edge("extract_map", END)

    return subgraph.compile()"""

    new_subgraph = """def create_transformation_subgraph(llm_runtime: LlmRuntimeAdapter) -> Any:
    \"\"\"
    Constructs a granular subgraph for the transformation phase.
    \"\"\"
    from langgraph.graph import StateGraph, END
    subgraph = StateGraph(AgentState)

    subgraph.add_node("extract_map", create_context_aware_extraction_node(llm_runtime))

    subgraph.set_entry_point("extract_map")
    subgraph.add_edge("extract_map", END)

    return subgraph.compile()"""

    if old_subgraph in content:
        content = content.replace(old_subgraph, new_subgraph)
        with open('backend/app/agent/graph.py', 'w') as f:
            f.write(content)
        print("Updated graph.py to remove prepare_schema")
    else:
        print("Could not find subgraph block in graph.py")

update_graph()
