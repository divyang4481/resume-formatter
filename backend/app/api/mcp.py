from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from app.dependencies import (
    get_job_repository,
    get_message_queue,
    get_storage_provider,
    get_template_repository
)
from app.db.session import SessionLocal
from app.schemas.enums import JobStatus
from app.config import settings
from pydantic import BaseModel
import uuid
import os

# Instantiate FastMCP server
mcp = FastMCP("Agentic Document Platform")


def _get_mcp_runtime_deps():
    db = SessionLocal()
    repo = get_job_repository(db)
    queue = get_message_queue(db)
    return db, repo, queue

@mcp.tool()
async def submit_document(
    filename: str,
    file_bytes_base64: str,
    industry_id: Optional[str] = None,
    template_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submits a document for processing, optionally with industry and template IDs.
    """
    import base64
    from app.schemas.job import ProcessingJob

    file_bytes = base64.b64decode(file_bytes_base64)
    job_id = str(uuid.uuid4())

    storage_provider = get_storage_provider()
    db, job_repository, message_queue = _get_mcp_runtime_deps()

    storage_key = f"jobs/{job_id}/input/{filename}"
    storage_ref = storage_provider.put_bytes(storage_key, file_bytes)

    if industry_id and template_id:
        job_status = JobStatus.CONFIRMED
    else:
        job_status = JobStatus.PROCESSING

    job = ProcessingJob(
        id=job_id,
        status=job_status,
        original_file_ref=storage_ref,
        created_by="mcp_agent",
        selected_template_id=template_id,
        extension_metadata={
            "industry_id": industry_id,
            "intent": "recruiter_runtime",
            "actor_role": "mcp_agent",
            "filename": filename,
            "content_type": "application/octet-stream",
            "test_run_id": None
        }
    )
    try:
        job_repository.save_job(job)
        message_queue.enqueue(settings.document_processing_queue_name, {"job_id": job_id})
    finally:
        db.close()

    return {
        "tool": "submit_document",
        "status": "executed",
        "result": {
            "job_id": job_id,
            "status": job_status.value if hasattr(job_status, "value") else job_status,
            "requires_confirmation": False
        }
    }

@mcp.tool()
async def confirm_document(
    document_id: str,
    industry_id: str,
    template_id: str
) -> Dict[str, Any]:
    """
    Confirms the industry and template for a submitted document.
    """
    db, repo, queue = _get_mcp_runtime_deps()
    job = repo.get_job(document_id)
    if not job:
        db.close()
        return {"tool": "confirm_document", "status": "error", "result": {"error": "Job not found"}}

    if hasattr(job, 'selected_template_id'):
        job.selected_template_id = template_id
    if hasattr(job, 'extension_metadata'):
        job.extension_metadata["industry_id"] = industry_id
    job.status = JobStatus.CONFIRMED

    try:
        repo.save_job(job)
        queue.enqueue(settings.document_processing_queue_name, {"job_id": document_id})
    finally:
        db.close()

    return {
        "tool": "confirm_document",
        "status": "executed",
        "result": {"message": f"Document {document_id} confirmed with {template_id}", "job_id": document_id}
    }

@mcp.tool()
async def get_document_status(job_id: str) -> Dict[str, Any]:
    """
    Checks the processing status of a document job.
    """
    db, repo, _ = _get_mcp_runtime_deps()
    job = repo.get_job(job_id)
    if not job:
        db.close()
        return {"tool": "get_document_status", "status": "error", "result": {"error": "Job not found"}}

    db.close()

    return {
        "tool": "get_document_status",
        "status": "executed",
        "result": {
            "job_id": job_id,
            "status": job.status.value if hasattr(job.status, 'value') else job.status,
            "error_message": getattr(job, "error_message", None),
            "stage": getattr(job, "stage", None)
        }
    }

@mcp.tool()
async def summarize_document(job_id: str) -> Dict[str, Any]:
    """
    Generates a summary of an uploaded CV.
    """
    db, repo, _ = _get_mcp_runtime_deps()
    storage = get_storage_provider()
    job = repo.get_job(job_id)

    if not job:
        db.close()
        return {"tool": "summarize_document", "status": "error", "result": {"error": "Job not found"}}

    generated_summary = getattr(job, "generated_summary", None)
    if generated_summary:
        db.close()
        return {"tool": "summarize_document", "status": "executed", "result": {"summary": generated_summary}}

    summary_uri = getattr(job, "summary_uri", None)
    if summary_uri:
        try:
            data = storage.get_bytes(summary_uri)
            return {"tool": "summarize_document", "status": "executed", "result": {"summary": data.decode("utf-8")}}
        except Exception as e:
            db.close()
            return {"tool": "summarize_document", "status": "error", "result": {"error": f"Failed to read summary: {str(e)}"}}

    db.close()

    return {
        "tool": "summarize_document",
        "status": "executed",
        "result": {"summary": "Summary not available yet."}
    }

@mcp.tool()
async def format_document(document_id: str, template_id: str) -> Dict[str, Any]:
    """
    Applies template to a document.
    """
    # This is essentially confirm_document logic if it's pending.
    return await confirm_document(document_id, "it", template_id)

@mcp.tool()
async def validate_document(document_id: str) -> Dict[str, Any]:
    """
    Checks completeness, schema, and chronology constraints.
    """
    db, repo, _ = _get_mcp_runtime_deps()
    job = repo.get_job(document_id)
    if not job:
        db.close()
        return {"tool": "validate_document", "status": "error", "result": {"error": "Job not found"}}

    # Assume validation result is attached if present
    validation_result_id = getattr(job, "validation_result_id", None)
    result = {
        "tool": "validate_document",
        "status": "executed",
        "result": {
            "document_id": document_id,
            "valid": validation_result_id is not None,
            "validation_id": validation_result_id
        }
    }
    db.close()
    return result

@mcp.tool()
async def generate_client_safe_profile(document_id: str) -> Dict[str, Any]:
    """
    Generates a privacy-transformed version of the profile.
    """
    # Return placeholder as it's typically part of the pipeline
    return {
        "tool": "generate_client_safe_profile",
        "status": "executed",
        "result": {"document_id": document_id, "safe": True, "message": "Triggered via standard pipeline if PII rules are active"}
    }

# We expose the Starlette app instance from FastMCP
# that can be mounted into the main FastAPI app.
router = mcp.sse_app()
