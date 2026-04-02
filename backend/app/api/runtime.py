from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status, Form, Header
import uuid
import os
from app.dependencies import (
    storage_provider_dependency,
    job_repository_dependency,
    llm_runtime_dependency,
    document_extraction_service_dependency,
    message_queue_dependency
)
from app.domain.interfaces import StorageProvider, JobRepository, DocumentExtractionService, ExtractionContext, MessageQueue
from app.schemas.job import ProcessingJob
from app.adapters.base import LlmRuntimeAdapter
from app.agent.graph import build_workflow_graph
from app.schemas.enums import JobStatus
from app.schemas.runtime import SubmitDocumentResponse, RuntimeJobStatusResponse, ConfirmDocumentRequest
from app.services.resume_ingestion_service import ResumeIngestionService

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".json", ".yaml", ".yml"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

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

import asyncio

def process_document_task(job_id: str, llm: LlmRuntimeAdapter, parser_service: DocumentExtractionService, job_repo: JobRepository):
    # Wrap in asyncio.run or just call async functions if we're in an async context.
    # BackgroundTasks runs synchronous functions if def is used.
    # To use async graph effectively, we should define this as async or use an event loop.
    # We will let fastapi run the async function.
    pass

from app.dependencies import get_storage_provider

async def async_process_document_task(job_id: str, llm: LlmRuntimeAdapter, parser_service: DocumentExtractionService, job_repo: JobRepository):
    # Build the graph injecting our adapters
    storage = get_storage_provider()
    graph = build_workflow_graph(llm_runtime=llm, doc_parser=parser_service, storage=storage)

    job = job_repo.get_job(job_id)
    if not job:
        return
    job.status = JobStatus.PROCESSING
    job_repo.save_job(job)

    # Reconstruct intent from job metadata
    ext_meta = getattr(job, 'extension_metadata', {})
    if not isinstance(ext_meta, dict):
        ext_meta = {}

    intent = ext_meta.get("intent", "candidate_runtime")
    actor_role = ext_meta.get("actor_role", "system")
    filename = ext_meta.get("filename", "mock_file.pdf")
    content_type = ext_meta.get("content_type", "application/pdf")

    # Actually, let's fetch original_file_ref
    file_ref = getattr(job, 'original_file_ref', "unknown")
    if file_ref == "unknown":
        if hasattr(job, 'candidate_resume_id'):
            file_ref = f"jobs/{job_id}/input/{filename}"

    selected_template_id = getattr(job, 'selected_template_id', getattr(job, 'template_asset_id', None))

    # Initial state
    initial_state = {
        "session_id": job_id,
        "file_path": file_ref,
        "file_type": "pdf",
        "extracted_text": None,
        "extraction_confidence": None,
        "canonical_model": None,
        "privacy_transformed_model": None,
        "selected_template_id": selected_template_id,
        "formatting_rules": None,
        "transformed_document_json": None,
        "validation_passed": False,
        "validation_errors": None,
        "summary_uri": None,
        "render_uri": None,
        "requires_human_review": False,
        "status": "ingested",
        # Custom state to pass down
        "intent": intent,
        "actor_role": actor_role,
        "filename": filename,
        "content_type": content_type
    }

    try:
        # Execute the workflow
        final_state = await graph.ainvoke(initial_state)

        # Persist final state back to job
        job.status = JobStatus.COMPLETED
        if final_state.get("summary_uri"):
            job.summary_uri = final_state["summary_uri"]
        if final_state.get("render_uri"):
            job.render_uri = final_state["render_uri"]

        job_repo.save_job(job)

    except Exception as e:
        print(f"Error executing graph: {e}")
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job_repo.save_job(job)

@router.post("/documents/submit", response_model=SubmitDocumentResponse)
async def submit_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    industry_id: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    x_processing_intent: str = Header("candidate_runtime", alias="X-Processing-Intent"),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    storage_provider: StorageProvider = Depends(storage_provider_dependency),
    job_repository: JobRepository = Depends(job_repository_dependency),
    llm_runtime: LlmRuntimeAdapter = Depends(llm_runtime_dependency),
    doc_parser_service: DocumentExtractionService = Depends(document_extraction_service_dependency),
    message_queue: MessageQueue = Depends(message_queue_dependency)
):
    """
    Accepts multipart upload for resume processing.
    Supports intent-based processing (candidate_runtime vs admin_sample_resume).
    """
    # Enforce role logic based on mock admin token
    actor_role = "recruiter"
    if x_admin_token == "admin-secret-token":
        actor_role = "admin"

    if x_processing_intent == "admin_sample_resume" and actor_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin access required for admin_sample_resume intent"
        )

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

    requires_confirmation = True
    suggested_industry_id = None
    suggested_template_id = None
    allowed_template_ids = None
    job_status = JobStatus.WAITING_FOR_CONFIRMATION

    if industry_id and template_id:
        requires_confirmation = False
        job_status = JobStatus.CONFIRMED
    else:
        # Suggest if not provided
        suggested_industry_id = "it"
        suggested_template_id = "tech-standard"
        allowed_template_ids = ["tech-standard", "tech-executive"]

    # Create job record
    job = ProcessingJob(
        id=job_id,
        status=job_status,
        original_file_ref=storage_ref,
        created_by=actor_role,
        selected_template_id=template_id if not requires_confirmation else None,
        extension_metadata={
            "industry_id": industry_id if not requires_confirmation else None,
            "intent": x_processing_intent,
            "actor_role": actor_role,
            "filename": filename,
            "content_type": file.content_type
        }
    )

    # Save job record
    job_repository.save_job(job)

    if not requires_confirmation:
        # Enqueue job to the message queue instead of using BackgroundTasks in-memory
        message_queue.enqueue("document_processing", {"job_id": job_id})

    return SubmitDocumentResponse(
        document_id=job_id,
        job_id=job_id,
        status=job_status,
        requires_confirmation=requires_confirmation,
        provided_industry_id=industry_id,
        provided_template_id=template_id,
        suggested_industry_id=suggested_industry_id,
        suggested_template_id=suggested_template_id,
        allowed_template_ids=allowed_template_ids,
        message="Document submitted successfully."
    )

@router.get("/jobs/{id}", response_model=RuntimeJobStatusResponse)
async def get_job_status(
    id: str,
    job_repository: JobRepository = Depends(job_repository_dependency)
):
    """
    Returns processing job status.
    """
    job = job_repository.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return RuntimeJobStatusResponse(
        job_id=job.id,
        status=job.status,
        original_file_ref="unknown" # Simplistic stub since original_file_ref is not on ProcessingJob model directly
    )

@router.post("/documents/{id}/confirm")
async def confirm_document(
    id: str,
    request: ConfirmDocumentRequest,
    job_repository: JobRepository = Depends(job_repository_dependency),
    message_queue: MessageQueue = Depends(message_queue_dependency)
):
    """
    Used to resume a paused human review step.
    """
    job = job_repository.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in (JobStatus.WAITING_FOR_CONFIRMATION, JobStatus.WAITING_FOR_CONFIRMATION.value):
        raise HTTPException(status_code=400, detail="Job is not waiting for confirmation")

    if hasattr(job, 'selected_template_id'):
        job.selected_template_id = request.template_id
    if hasattr(job, 'extension_metadata'):
        job.extension_metadata["industry_id"] = request.industry_id
    job.status = JobStatus.CONFIRMED

    job_repository.save_job(job)

    # Enqueue job to the message queue to resume processing
    message_queue.enqueue("document_processing", {"job_id": id})

    return {"message": "Document confirmed", "job_id": id, "status": job.status}

@router.get("/documents/{id}/stream")
async def stream_events(id: str):
    """
    SSE or WebSocket progress stream.
    """
    return {"message": "Streaming endpoint not fully implemented"}

from fastapi.responses import Response

@router.get("/documents/{id}/download")
async def download_output(
    id: str,
    job_repository: JobRepository = Depends(job_repository_dependency),
    storage_provider: StorageProvider = Depends(storage_provider_dependency)
):
    """
    Download final output.
    """
    job = job_repository.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    render_uri = getattr(job, "render_uri", None)
    if not render_uri:
        raise HTTPException(status_code=404, detail="Rendered output not found for this job")

    try:
        data = storage_provider.get_bytes(render_uri)
        return Response(content=data, media_type="text/markdown") # For now we return markdown as mock
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve output: {e}")

from fastapi import Request

@router.get("/jobs/{id}/output")
async def get_job_output(
    id: str,
    request: Request,
    job_repository: JobRepository = Depends(job_repository_dependency),
    storage_provider: StorageProvider = Depends(storage_provider_dependency)
):
    job = job_repository.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    render_uri = getattr(job, "render_uri", None)
    if not render_uri:
        return {"message": "Output not available", "url": ""}

    # We return the URL that points back to our own download endpoint
    # In a real system with S3, this might be a pre-signed URL generated by storage_provider
    url = str(request.url_for('download_output', id=id))
    return {"message": "Success", "url": url}

@router.get("/jobs/{id}/summary")
async def get_job_summary(
    id: str,
    job_repository: JobRepository = Depends(job_repository_dependency),
    storage_provider: StorageProvider = Depends(storage_provider_dependency)
):
    """
    Returns summary of the processed CV.
    """
    job = job_repository.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    status_val = job.status.value if hasattr(job.status, 'value') else job.status
    if status_val == JobStatus.COMPLETED.value or status_val == JobStatus.COMPLETED:
        summary_uri = getattr(job, "summary_uri", None)
        if summary_uri:
            try:
                data = storage_provider.get_bytes(summary_uri)
                return {"summary": data.decode("utf-8")}
            except Exception as e:
                print(f"Failed to read summary from storage: {e}")
                return {"summary": "Summary file exists but could not be read."}

        return {"summary": "Summary missing from completed job."}
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
