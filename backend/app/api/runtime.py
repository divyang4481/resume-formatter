from fastapi import APIRouter, Depends, BackgroundTasks
import uuid
from app.dependencies import llm_runtime_dependency, document_parser_dependency
from app.adapters.base import LlmRuntimeAdapter, DocumentParserAdapter
from app.agent.graph import build_workflow_graph

router = APIRouter()

# In-memory store for session states (for mock purposes)
SESSIONS = {}

@router.post("/documents/submit")
async def submit_document(
    background_tasks: BackgroundTasks,
    llm_runtime: LlmRuntimeAdapter = Depends(llm_runtime_dependency),
    doc_parser: DocumentParserAdapter = Depends(document_parser_dependency)
):
    """
    Accepts multipart upload or base64 payload.
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

    return {"message": "Document submitted", "session_id": session_id}

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
    return {"message": "Download endpoint not fully implemented"}

@router.post("/documents/{id}/feedback")
async def submit_feedback(id: str):
    """
    Submit feedback on generated document.
    """
    return {"message": "Feedback received"}
