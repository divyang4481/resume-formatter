from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from typing import Optional
import uuid

from app.dependencies import get_job_repository, get_storage_provider, get_message_queue, get_template_repository
from app.db.models import ProcessingJob, CandidateResume

router = APIRouter()

@router.post("/resumes/upload")
async def upload_resume(
    file: UploadFile = File(...),
    storage = Depends(get_storage_provider),
    job_repo = Depends(get_job_repository)
):
    """Stateless upload, returns WAITING_FOR_CONFIRMATION."""
    file_bytes = await file.read()
    job_id = str(uuid.uuid4())
    key = f"jobs/{job_id}/input/{file.filename}"

    uri = storage.put_bytes(file_bytes, key, file.content_type)

    # Store candidate resume
    resume_id = str(uuid.uuid4())
    resume = CandidateResume(
        id=resume_id,
        source_file_name=file.filename,
        source_storage_uri=uri
    )
    job_repo.db.add(resume)

    # Create job
    job = ProcessingJob(
        id=job_id,
        candidate_resume_id=resume_id,
        original_file_ref=uri,
        status="WAITING_FOR_CONFIRMATION",
        stage="init",
        job_type="RESUME_FORMATTING"
    )
    job_repo.db.add(job)
    job_repo.db.commit()

    return {
        "job_id": job_id,
        "status": "WAITING_FOR_CONFIRMATION",
        "file_uri": uri,
        "message": "Resume uploaded. Confirm processing to continue."
    }

@router.post("/resumes/{job_id}/confirm")
async def confirm_processing(
    job_id: str,
    job_repo = Depends(get_job_repository),
    queue = Depends(get_message_queue)
):
    """Pushes job to SQS queue to be processed by ECS worker."""
    job = job_repo.db.query(ProcessingJob).filter_by(id=job_id).first()
    if not job or job.status != "WAITING_FOR_CONFIRMATION":
        raise HTTPException(status_code=400, detail="Invalid job or job already confirmed.")

    job.status = "QUEUED"
    job_repo.db.commit()

    queue.publish({
        "job_id": job_id,
        "job_type": job.job_type,
        "input_uri": job.original_file_ref
    })

    return {
        "job_id": job_id,
        "status": "QUEUED"
    }

@router.get("/resumes/{job_id}/status")
async def get_job_status(job_id: str, job_repo = Depends(get_job_repository)):
    job = job_repo.db.query(ProcessingJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.id,
        "status": job.status,
        "stage": job.stage,
        "error_message": job.error_message,
        "artifacts": {
            "docx": job.render_docx_uri,
            "summary": job.summary_uri
        }
    }
