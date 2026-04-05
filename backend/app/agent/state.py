from typing import TypedDict, Annotated, Optional, Dict, Any, List

class AgentState(TypedDict, total=False):
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
    raw_parsed_data: Optional[Dict[str, Any]] # Structured sections/tables from Docling/etc


    # Triage / classification
    document_kind: Optional[str]
    document_confidence: Optional[float]
    document_reason: Optional[str]

    # Template suggestion
    suggested_template_id: Optional[str]
    suggested_template_ids: Optional[List[str]]
    suggested_template_scores: Optional[List[Dict[str, Any]]]
    template_resolution_mode: Optional[str]
    awaiting_confirmation: Optional[bool]

    # Normalized JSON dictionary
    canonical_model: Optional[Dict[str, Any]]

    # Privacy transformed representation
    privacy_transformed_model: Optional[Dict[str, Any]]

    # Template and Formatting rules
    selected_template_id: Optional[str]
    template_storage_uri: Optional[str]
    template_text: Optional[str]
    formatting_rules: Optional[str]
    summary_guidance: Optional[str]
    formatting_guidance: Optional[str]
    validation_guidance: Optional[str]
    pii_guidance: Optional[str]
    
    # Governance Requirements
    expected_sections: Optional[str]
    expected_fields: Optional[str]

     # LLM Transformation results
    transformed_document_json: Optional[str]
    linearized_data: Optional[str]

    # Contextual guidance and metadata
    field_extraction_manifest: Optional[Dict[str, Any]]
    industry: Optional[str]
    language: Optional[str]
    
    # Validation
    validation_passed: bool
    validation_report: Optional[str]
    validation_errors: Optional[list]
    validation_warnings: Optional[list]


    # Output Artifacts
    summary_text: Optional[str]
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
