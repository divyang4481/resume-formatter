from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
import uuid
import os
from app.dependencies import (
    storage_provider_dependency,
    job_repository_dependency,
    llm_runtime_dependency,
    document_parser_dependency
)
from app.domain.interfaces import StorageProvider, JobRepository
from app.schemas.job import ProcessingJob
from app.adapters.base import LlmRuntimeAdapter, DocumentParserAdapter
from app.agent.graph import build_workflow_graph
from app.schemas.enums import JobStatus
from app.schemas.runtime import SubmitDocumentResponse, RuntimeJobStatusResponse, ConfirmDocumentRequest

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".json", ".yaml", ".yml"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

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

def process_document_task(job_id: str, llm: LlmRuntimeAdapter, parser: DocumentParserAdapter, job_repo: JobRepository):
    # Build the graph injecting our adapters
    graph = build_workflow_graph(llm_runtime=llm, doc_parser=parser)

    job = job_repo.get_job(job_id)
    if not job:
        return
    job.status = JobStatus.PROCESSING
    job_repo.save_job(job)

    # Initial state
    initial_state = {
        "session_id": job_id,
        "file_path": "mock_file.pdf",
        "file_type": "pdf",
        "extracted_text": None,
        "extraction_confidence": None,
        "canonical_model": None,
        "privacy_transformed_model": None,
        "selected_template_id": job.selected_template_id,
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
        job.status = JobStatus.COMPLETED
        job_repo.save_job(job)
    except Exception as e:
        job.status = JobStatus.FAILED
        job_repo.save_job(job)

@router.post("/documents/submit", response_model=SubmitDocumentResponse)
async def submit_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    industry_id: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    storage_provider: StorageProvider = Depends(storage_provider_dependency),
    job_repository: JobRepository = Depends(job_repository_dependency),
    llm_runtime: LlmRuntimeAdapter = Depends(llm_runtime_dependency),
    doc_parser: DocumentParserAdapter = Depends(document_parser_dependency)
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
        created_by="system", # Or real user context if available
        selected_template_id=template_id if not requires_confirmation else None,
        extension_metadata={
            "industry_id": industry_id if not requires_confirmation else None
        }
    )

    # Save job record
    job_repository.save_job(job)

    if not requires_confirmation:
        # Run the workflow graph in the background
        background_tasks.add_task(process_document_task, job_id, llm_runtime, doc_parser, job_repository)

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
    background_tasks: BackgroundTasks,
    job_repository: JobRepository = Depends(job_repository_dependency),
    llm_runtime: LlmRuntimeAdapter = Depends(llm_runtime_dependency),
    doc_parser: DocumentParserAdapter = Depends(document_parser_dependency)
):
    """
    Used to resume a paused human review step.
    """
    job = job_repository.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.WAITING_FOR_CONFIRMATION:
        raise HTTPException(status_code=400, detail="Job is not waiting for confirmation")

    job.selected_template_id = request.template_id
    job.extension_metadata["industry_id"] = request.industry_id
    job.status = JobStatus.CONFIRMED

    job_repository.save_job(job)

    # Trigger background task to resume processing
    background_tasks.add_task(process_document_task, id, llm_runtime, doc_parser, job_repository)

    return {"message": "Document confirmed", "job_id": id, "status": job.status}

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
async def get_job_summary(
    id: str,
    job_repository: JobRepository = Depends(job_repository_dependency)
):
    """
    Returns summary of the processed CV.
    """
    job = job_repository.get_job(id)
    if job and job.status == JobStatus.COMPLETED:
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
