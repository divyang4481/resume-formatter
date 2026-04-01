from fastapi import APIRouter

router = APIRouter()

@router.post("/documents/submit")
async def submit_document():
    """
    Accepts multipart upload or base64 payload.
    Returns session_id, status, and initial metadata.
    """
    return {"message": "Document submitted", "session_id": "1234"}

@router.get("/documents/{id}/status")
async def get_session_status(id: str):
    """
    Returns processing status, current stage, warnings, and final metadata.
    """
    return {"session_id": id, "status": "processing"}

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
