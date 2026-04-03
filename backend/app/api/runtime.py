from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status, Form, Header
import uuid
import os
from app.dependencies import (
    storage_provider_dependency,
    job_repository_dependency,
    llm_runtime_dependency,
    document_extraction_service_dependency,
    message_queue_dependency,
    template_repository_dependency,
    template_lookup_service_dependency,
    resume_workflow_service_dependency
)
from app.domain.interfaces import StorageProvider, JobRepository, DocumentExtractionService, MessageQueue, TemplateRepository
from app.schemas.job import ProcessingJob
from app.adapters.base import LlmRuntimeAdapter
from app.agent.graph import AgentState
from app.schemas.enums import JobStatus
from app.schemas.runtime import SubmitDocumentResponse, RuntimeJobStatusResponse, ConfirmDocumentRequest
from app.services.resume_ingestion_service import ResumeIngestionService
from app.services.resume_workflow_service import ResumeWorkflowService

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".json", ".yaml", ".yml"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

from typing import Optional, List

from app.services.template_lookup_service import TemplateLookupService

@router.get("/lookups/industries")
async def get_industries(
    template_lookup_service: TemplateLookupService = Depends(template_lookup_service_dependency)
):
    """
    Returns available industries for form selection from published templates.
    """
    industries_list = template_lookup_service.list_active_industries()
    return {"industries": industries_list}

@router.get("/lookups/templates")
async def get_templates(
    industry: Optional[str] = None,
    template_lookup_service: TemplateLookupService = Depends(template_lookup_service_dependency)
):
    """
    Returns available templates from the database, optionally filtered by industry.
    """
    templates = template_lookup_service.list_active_templates(industry)
    return {"templates": templates}

import asyncio

def process_document_task(job_id: str, llm: LlmRuntimeAdapter, parser_service: DocumentExtractionService, job_repo: JobRepository):
    # Wrap in asyncio.run or just call async functions if we're in an async context.
    # BackgroundTasks runs synchronous functions if def is used.
    # To use async graph effectively, we should define this as async or use an event loop.
    # We will let fastapi run the async function.
    pass

# Workflow migrated to ResumeWorkflowService

# End of migrated workflow


from app.schemas.runtime import ExecutionContext
from app.schemas.enums import ExecutionMode
from app.services.template_resolution_service import TemplateResolutionService
from app.domain.interfaces import ExtractionContext
from app.db.session import SessionLocal
from app.db.models import TemplateTestRun

@router.post("/documents/submit", response_model=SubmitDocumentResponse)
async def submit_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    industry_id: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    x_execution_mode: str = Header(ExecutionMode.RECRUITER_RUNTIME.value, alias="X-Execution-Mode"),
    x_actor_role: str = Header("recruiter", alias="X-Actor-Role"),
    storage_provider: StorageProvider = Depends(storage_provider_dependency),
    job_repository: JobRepository = Depends(job_repository_dependency),
    llm_runtime: LlmRuntimeAdapter = Depends(llm_runtime_dependency),
    doc_parser_service: DocumentExtractionService = Depends(document_extraction_service_dependency),
    message_queue: MessageQueue = Depends(message_queue_dependency),
    template_repository: TemplateRepository = Depends(template_repository_dependency)
):
    """
    Accepts multipart upload for resume processing.
    Supports execution modes (recruiter_runtime vs admin_template_test).
    """
    try:
        execution_mode = ExecutionMode(x_execution_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid execution mode: {x_execution_mode}")

    if execution_mode == ExecutionMode.ADMIN_TEMPLATE_TEST and template_id is None:
        raise HTTPException(
            status_code=400,
            detail="templateId is mandatory for admin_template_test mode"
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

    test_run_id = None
    if execution_mode == ExecutionMode.ADMIN_TEMPLATE_TEST:
        test_run_id = str(uuid.uuid4())
        storage_key = f"templates/{template_id}/tests/{test_run_id}/input/{filename}"
    else:
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
        # Suggest if not provided using shared service
        try:
            # Synchronous extraction
            extracted = await doc_parser_service.extract(
                file_bytes=file_bytes,
                filename=filename,
                content_type=file.content_type,
                context=ExtractionContext(intent=execution_mode.value, actor_role=x_actor_role)
            )

            # Use TemplateResolutionService
            resolution_service = TemplateResolutionService(llm_runtime, template_repository)
            rec_result = await resolution_service.recommend_template(
                extracted_text=extracted.extracted_text,
                industry_id=industry_id,
                mode=execution_mode.value
            )

            suggested_industry_id = rec_result.suggested_industry_id
            suggested_template_id = rec_result.suggested_template_id
            allowed_template_ids = rec_result.allowed_template_ids
        except Exception as e:
            print(f"Failed to get LLM template recommendation: {e}")
            # Fallback
            suggested_industry_id = "it"
            suggested_template_id = "general_cv_v1"
            allowed_template_ids = ["general_cv_v1"]
        
        # FORCET: Automatically accept suggestions and move to processing
        requires_confirmation = False
        job_status = JobStatus.CONFIRMED
        template_id = suggested_template_id
        industry_id = suggested_industry_id

    # Create job record
    job = ProcessingJob(
        id=job_id,
        status=job_status,
        original_file_ref=storage_ref,
        created_by=x_actor_role,
        selected_template_id=template_id if not requires_confirmation else None,
        extension_metadata={
            "industry_id": industry_id if not requires_confirmation else None,
            "intent": execution_mode.value,
            "actor_role": x_actor_role,
            "filename": filename,
            "content_type": file.content_type,
            "test_run_id": test_run_id
        }
    )

    # Save job record
    job_repository.save_job(job)

    # Create TemplateTestRun if in test mode
    if execution_mode == ExecutionMode.ADMIN_TEMPLATE_TEST:
        db = SessionLocal()
        try:
            test_run = TemplateTestRun(
                id=test_run_id,
                template_id=template_id,
                processing_job_id=job_id,
                created_by=x_actor_role
            )
            db.add(test_run)
            db.commit()
        finally:
            db.close()

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
        original_file_ref=getattr(job, "original_file_ref", "unknown"),
        stage=getattr(job, "stage", None),
        error_message=getattr(job, "error_message", None)
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

    render_docx_uri = getattr(job, "render_docx_uri", None)
    if not render_docx_uri:
        raise HTTPException(status_code=404, detail="Rendered output not found for this job")

    try:
        data = storage_provider.get_bytes(render_docx_uri)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="formatted_resume_{job.id}.docx"'}
        )
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

    render_docx_uri = getattr(job, "render_docx_uri", None)
    if not render_docx_uri:
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
        # 1. Try to get summary text directly from DB
        generated_summary = getattr(job, "generated_summary", None)
        if generated_summary:
            return {"summary": generated_summary}

        # 2. Fallback to reading from summary_uri in storage
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
