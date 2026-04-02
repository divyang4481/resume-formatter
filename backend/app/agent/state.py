from typing import TypedDict, Annotated, Optional, Dict, Any

class AgentState(TypedDict):
    """
    Defines the global state schema for the document processing workflow.
    This state object is passed through the LangGraph nodes.
    """
    session_id: str
    file_path: str
    file_type: str

    # Extraction output
    extracted_text: Optional[str]
    extraction_confidence: Optional[float]

    # Normalized JSON dictionary
    canonical_model: Optional[Dict[str, Any]]

    # Privacy transformed representation
    privacy_transformed_model: Optional[Dict[str, Any]]

    # Template and Formatting rules
    selected_template_id: Optional[str]
    formatting_rules: Optional[str]

    # LLM Transformation results
    transformed_document_json: Optional[str]

    # Validation
    validation_passed: bool
    validation_errors: Optional[list]

    # Output Artifacts
    summary_uri: Optional[str]
    render_uri: Optional[str]
    render_docx_uri: Optional[str]

    # Orchestration control variables
    requires_human_review: bool
    status: str

    # Intent variables passed from router
    intent: Optional[str]
    actor_role: Optional[str]
    filename: Optional[str]
    content_type: Optional[str]

    # Additional contextual metadata
    runtime_metadata: Optional[Dict[str, Any]]
