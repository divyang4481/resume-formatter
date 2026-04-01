from fastapi import APIRouter, Depends, BackgroundTasks
import uuid
from app.dependencies import llm_runtime_dependency, document_parser_dependency
from app.adapters.base import LlmRuntimeAdapter, DocumentParserAdapter
from app.agent.graph import build_workflow_graph

router = APIRouter()

# In-memory store for session states (for mock purposes)
SESSIONS = {}

from fastapi import UploadFile, File, Form
from typing import Optional, List

@router.get("/lookups/industries")
async def get_industries():
    """
    Returns available industries for form selection.
    """
    return {
        "industries": [
            {"id": "it", "name": "Information Technology"},
            {"id": "finance", "name": "Finance & Accounting"},
            {"id": "healthcare", "name": "Healthcare"}
        ]
    }

@router.get("/lookups/templates")
async def get_templates(industry: Optional[str] = None):
    """
    Returns available templates, optionally filtered by industry.
    """
    all_templates = [
        {"id": "tech-standard", "name": "Tech Standard", "industry": "it"},
        {"id": "tech-executive", "name": "Tech Executive", "industry": "it"},
        {"id": "finance-basic", "name": "Finance Basic", "industry": "finance"},
        {"id": "medical-pro", "name": "Medical Professional", "industry": "healthcare"},
        {"id": "general", "name": "General Clean", "industry": "general"}
    ]

    if industry:
        templates = [t for t in all_templates if t["industry"] == industry or t["industry"] == "general"]
    else:
        templates = all_templates

    return {"templates": templates}

@router.post("/documents/submit")
async def submit_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    industry: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    candidate_name: Optional[str] = Form(None),
    llm_runtime: LlmRuntimeAdapter = Depends(llm_runtime_dependency),
    doc_parser: DocumentParserAdapter = Depends(document_parser_dependency)
):
    """
    Accepts multipart upload.
    Returns session_id, status, and initial metadata.
    """
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {"status": "processing", "state": {}}

    def process_document(session_id: str, llm: LlmRuntimeAdapter, parser: DocumentParserAdapter):
        # Build the graph injecting our adapters
        graph = build_workflow_graph(llm_runtime=llm, doc_parser=parser)

        # Initial state
        initial_state = {
            "session_id": session_id,
            "file_path": "mock_file.pdf",
            "file_type": "pdf",
            "extracted_text": None,
            "extraction_confidence": None,
            "canonical_model": None,
            "privacy_transformed_model": None,
            "selected_template_id": None,
            "formatting_rules": None,
            "transformed_document_json": None,
            "validation_passed": False,
            "validation_errors": None,
            "requires_human_review": False,
            "status": "ingested"
        }

        try:
            # Execute the workflow
            final_state = graph.invoke(initial_state)
            SESSIONS[session_id] = {"status": "completed", "state": final_state}
        except Exception as e:
            SESSIONS[session_id] = {"status": "failed", "error": str(e)}

    # Run the workflow graph in the background
    background_tasks.add_task(process_document, session_id, llm_runtime, doc_parser)

    # Note: using session_id as job_id here
    return {
        "message": "Document submitted",
        "session_id": session_id,
        "job_id": session_id
    }

@router.get("/jobs/{id}")
async def get_job_status(id: str):
    """
    Alias for document status using standard job routing.
    """
    return await get_session_status(id)

@router.get("/documents/{id}/status")
async def get_session_status(id: str):
    """
    Returns processing status, current stage, warnings, and final metadata.
    """
    session = SESSIONS.get(id, {"status": "not_found"})
    return {"session_id": id, "status": session.get("status"), "details": session}

@router.post("/documents/{id}/confirm")
async def confirm_document(id: str):
    """
    Used to resume a paused human review step.
    """
    return {"message": "Document confirmed", "session_id": id}

@router.get("/documents/{id}/stream")
async def stream_events(id: str):
    """
    SSE or WebSocket progress stream.
    """
    return {"message": "Streaming endpoint not fully implemented"}

@router.get("/documents/{id}/download")
async def download_output(id: str):
    """
    Download final output.
    """
    return {"message": "Download endpoint not fully implemented", "url": f"http://example.com/download/{id}.pdf"}

@router.get("/jobs/{id}/output")
async def get_job_output(id: str):
    return await download_output(id)

@router.get("/jobs/{id}/summary")
async def get_job_summary(id: str):
    """
    Returns summary of the processed CV.
    """
    session = SESSIONS.get(id, {})
    # For mock purposes
    if session.get("status") == "completed":
        return {
            "summary": "This candidate shows strong experience in their field with over 5 years of progressive responsibility. Key skills align well with the selected template and industry standards. PII has been successfully redacted."
        }
    return {"summary": "Summary not available yet."}

@router.post("/documents/{id}/feedback")
async def submit_feedback(id: str):
    """
    Submit feedback on generated document.
    """
    return {"message": "Feedback received"}

@router.post("/jobs/{id}/feedback")
async def submit_job_feedback(id: str):
    return await submit_feedback(id)
