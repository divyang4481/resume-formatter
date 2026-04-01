from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
import uuid
import os
from app.dependencies import storage_provider_dependency, job_repository_dependency
from app.domain.interfaces import StorageProvider, JobRepository
from app.schemas.job import ProcessingJob
from app.schemas.enums import JobStatus
from app.schemas.runtime import RuntimeDocumentSubmitResponse, RuntimeJobStatusResponse

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".json", ".yaml", ".yml"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

@router.post("/documents/submit", response_model=RuntimeDocumentSubmitResponse)
async def submit_document(
    file: UploadFile = File(...),
    storage_provider: StorageProvider = Depends(storage_provider_dependency),
    job_repository: JobRepository = Depends(job_repository_dependency)
):
    """
    Accepts multipart upload for candidate resume processing.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/markdown",
        "text/plain",
        "application/json",
        "application/yaml",
        "application/x-yaml",
        "text/yaml"
    }

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported MIME type: {file.content_type}")


    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty.")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 25 MB limit.")

    job_id = str(uuid.uuid4())
    filename = os.path.basename(file.filename)
    storage_key = f"jobs/{job_id}/input/{filename}"

    # Store file via storage provider
    storage_ref = storage_provider.put_bytes(storage_key, file_bytes)

    # Create job record
    job = ProcessingJob(
        id=job_id,
        status=JobStatus.PENDING,
        original_file_ref=storage_ref,
        created_by="system" # Or real user context if available
    )

    # Save job record
    job_repository.save_job(job)

    return RuntimeDocumentSubmitResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message="Document submitted successfully and job initialized."
    )

@router.get("/jobs/{job_id}", response_model=RuntimeJobStatusResponse)
async def get_job_status(
    job_id: str,
    job_repository: JobRepository = Depends(job_repository_dependency)
):
    """
    Returns processing job status.
    """
    job = job_repository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return RuntimeJobStatusResponse(
        job_id=job.id,
        status=job.status,
        original_file_ref=job.original_file_ref
    )


@router.get("/documents/{id}/status")
async def get_session_status(id: str):
    """
    Legacy endpoint. Use /jobs/{id} instead.
    """
    return {"session_id": id, "status": "deprecated"}

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
