import logging
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from pydantic import ValidationError
from app.schemas.enums import JobStatus
import json
import uuid

logger = logging.getLogger(__name__)

from app.schemas.admin import AssetUploadRequestMetadata, AssetUploadResponse
from app.schemas.enums import AssetStatus
from app.dependencies import (
    mock_is_admin,
    get_storage_provider,
    get_template_repository,
    get_message_queue,
    get_document_extraction_service,
    get_knowledge_index,
    get_llm_runtime,
)
from app.utils import validate_uploaded_file
from app.services.template_service import TemplateService
from app.domain.interfaces import (
    StorageProvider,
    TemplateRepository,
    EventBus,
    DocumentExtractionService,
    KnowledgeIndex,
)
from app.domain.interfaces import LlmRuntimeAdapter
from app.config import settings

router = APIRouter()


@router.post("/templates/upload", response_model=AssetUploadResponse)
async def upload_asset(
    file: UploadFile = File(...),
    metadata: str = Form(..., description="JSON string of AssetUploadRequestMetadata"),
    is_admin: bool = Depends(mock_is_admin),
    storage_provider: StorageProvider = Depends(get_storage_provider),
    template_repository: TemplateRepository = Depends(get_template_repository),
    event_bus: EventBus = Depends(get_message_queue),
    extraction_service: DocumentExtractionService = Depends(
        get_document_extraction_service
    ),
    knowledge_index: KnowledgeIndex = Depends(get_knowledge_index),
    llm: LlmRuntimeAdapter = Depends(get_llm_runtime),
):
    try:
        # Validate metadata JSON
        metadata_dict = json.loads(metadata)
        parsed_metadata = AssetUploadRequestMetadata(**metadata_dict)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format in metadata field",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors()
        )

    # Validate file
    await validate_uploaded_file(file)

    # Read the file content bytes
    content = await file.read()

    # 1. Store the raw file immediately
    import uuid
    from app.db.session import SessionLocal
    from app.db.models import ProcessingJob, TemplateAsset

    asset_id = str(uuid.uuid4())
    storage_key = f"templates/{asset_id}/{file.filename}"
    storage_uri = storage_provider.put_bytes(content, storage_key)

    db = SessionLocal()
    try:
        # 2. Create the Draft Template Record
        template = TemplateAsset(
            id=asset_id,
            version="1.0.0",
            name=parsed_metadata.name or file.filename,
            status=AssetStatus.DRAFT.value,
            industry=parsed_metadata.industry,
            role_family=parsed_metadata.role_family,
            region=parsed_metadata.region,
            language=parsed_metadata.language,
            storage_uri=storage_uri,
            file_name=file.filename,
            created_by="admin-user",
        )
        db.add(template)
        db.flush()  # Ensure template exists for foreign key constraint before adding job

        # 3. Create a processing job for the worker
        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            original_file_ref=storage_uri,
            template_asset_id=asset_id,
            template_version="1.0.0",
            status=JobStatus.PROCESSING.value,
            stage="init",
            job_type="TEMPLATE_PROCESSING",
        )
        db.add(job)
        db.commit()

        # 4. Enqueue the Job
        from app.dependencies import get_message_queue

        queue = get_message_queue()
        message_body = {
                "job_id": job_id,
                "job_type": "TEMPLATE_PROCESSING",
                "input_uri": storage_uri,
                "template_id": asset_id,
                "version_id": "1.0.0",
            }
        logger.info(f"--- PUBLISHING TEMPLATE JOB TO SQS ---")
        logger.info(f"Queue: {settings.sqs_processing_queue_url}")
        logger.info(f"Message Body: {message_body}")
        
        queue.publish(message_body)
        logger.info(f"Successfully enqueued template job {job_id} for asset {asset_id}")

    finally:
        db.close()

    return AssetUploadResponse(
        asset_id=asset_id,
        status=AssetStatus.DRAFT,  # The entity is still a draft while processing
        message="Asset uploaded successfully. Processing in background.",
    )


@router.get("/templates")
async def pull_templates(
    template_repository: TemplateRepository = Depends(get_template_repository),
    is_admin: bool = Depends(mock_is_admin),
):
    templates = template_repository.list_templates({})
    return {"templates": [t.model_dump() for t in templates]}


from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import TemplateAsset, TemplateTestRun
from app.services.template_publish_guard import TemplatePublishGuard


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    role_family: Optional[str] = None
    language: Optional[str] = None
    notes: Optional[str] = None
    purpose: Optional[str] = None
    expected_sections: Optional[str] = None
    expected_fields: Optional[str] = None
    field_extraction_manifest: Optional[str] = None

    summary_guidance: Optional[str] = None
    formatting_guidance: Optional[str] = None
    validation_guidance: Optional[str] = None
    pii_guidance: Optional[str] = None
    selection_weight: Optional[int] = None
    is_default_for_industry: Optional[bool] = None


@router.patch("/templates/{id}")
async def update_template(
    id: str, payload: TemplateUpdateRequest, is_admin: bool = Depends(mock_is_admin)
):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "field_extraction_manifest" and value is not None:
                setattr(template, key, json.dumps(value))
            else:
                setattr(template, key, value)

        db.commit()
        return {"message": "Template updated successfully"}
    finally:
        db.close()


from app.services.template_analysis_service import TemplateAnalysisService


@router.post("/templates/{id}/analyze")
async def analyze_template(
    id: str,
    is_admin: bool = Depends(mock_is_admin),
    storage_provider: StorageProvider = Depends(get_storage_provider),
    extraction_service: DocumentExtractionService = Depends(
        get_document_extraction_service
    ),
    llm: LlmRuntimeAdapter = Depends(get_llm_runtime),
):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        if not template.storage_uri:
            raise HTTPException(
                status_code=400, detail="Template file not found in storage"
            )

        # Fetch template bytes
        template_key = template.storage_uri.replace("local://", "")
        template_bytes = storage_provider.get_bytes(template_key)

        from app.services.resume_ai_service import ResumeAiService

        ai_service = ResumeAiService(llm, extraction_service)
        analyzer = TemplateAnalysisService(ai_service=ai_service)
        suggestions = await analyzer.analyze_template(
            template_bytes, template.file_name or "template.docx"
        )

        return {"template_id": id, "suggestions": suggestions}
    finally:
        db.close()


@router.get("/templates/{id}")
async def get_template_detail(id: str, is_admin: bool = Depends(mock_is_admin)):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        latest_test_run = (
            db.query(TemplateTestRun)
            .filter(TemplateTestRun.template_id == id)
            .order_by(TemplateTestRun.created_at.desc())
            .first()
        )

        validation_result = {}
        if latest_test_run and latest_test_run.validation_result_json:
            validation_result = json.loads(latest_test_run.validation_result_json)

        publish_check = TemplatePublishGuard.can_publish(
            template, latest_test_run, validation_result
        )

        return {
            "template": {
                "id": template.id,
                "name": template.name,
                "status": template.status,
                "notes": template.notes,
                "purpose": template.purpose,
                "expected_sections": template.expected_sections,
                "expected_fields": template.expected_fields,
                "field_extraction_manifest": json.loads(template.field_extraction_manifest) if template.field_extraction_manifest else [],
                "summary_guidance": template.summary_guidance,
                "formatting_guidance": template.formatting_guidance,
                "validation_guidance": template.validation_guidance,
                "pii_guidance": template.pii_guidance,
                "selection_weight": template.selection_weight,
                "field_extraction_manifest": template.field_extraction_manifest,
                "industry": template.industry,
                "language": template.language,
                "role_family": template.role_family,
                "updated_at": template.updated_at,
            },
            "latest_test_run": (
                {
                    "id": latest_test_run.id,
                    "decision": latest_test_run.decision,
                    "created_at": latest_test_run.created_at,
                }
                if latest_test_run
                else None
            ),
            "publish_eligibility": {
                "can_publish": publish_check.can_publish,
                "reason": publish_check.reason,
            },
        }
    finally:
        db.close()


@router.get("/templates/{id}/test-runs")
async def list_template_test_runs(id: str, is_admin: bool = Depends(mock_is_admin)):
    from app.db.models import ProcessingJob, CandidateResume

    db = SessionLocal()
    try:
        # Join with ProcessingJob and CandidateResume to get extraction facts and mapping results
        query = (
            db.query(TemplateTestRun, ProcessingJob, CandidateResume)
            .join(ProcessingJob, TemplateTestRun.processing_job_id == ProcessingJob.id)
            .outerjoin(CandidateResume, ProcessingJob.candidate_resume_id == CandidateResume.id)
            .filter(TemplateTestRun.template_id == id)
            .order_by(TemplateTestRun.created_at.desc())
        )
        
        runs = query.all()
        import json

        result = []
        for r_run, r_job, r_resume in runs:
            val_json = {}
            if r_run.validation_result_json:
                try:
                    val_json = json.loads(r_run.validation_result_json)
                except Exception:
                    pass

            # Parse extracted facts and transformed mapping
            facts_json = {}
            if r_resume and r_resume.candidate_facts_json:
                try:
                    facts_json = json.loads(r_resume.candidate_facts_json)
                except Exception:
                    pass
            
            mapping_json = {}
            if r_job and r_job.transformed_json:
                try:
                    mapping_json = json.loads(r_job.transformed_json)
                except Exception:
                    pass

            # Direct query fallback to ensure we get the job summary if missing on test run
            summary = r_run.generated_summary or r_job.generated_summary

            result.append(
                {
                    "id": r_run.id,
                    "job_id": r_run.processing_job_id,
                    "decision": r_run.decision,
                    "created_at": r_run.created_at,
                    "reviewed_at": r_run.reviewed_at,
                    "sample_resume_asset_id": r_run.sample_resume_asset_id,
                    "generated_summary": summary,
                    "validation_result": val_json,
                    "extraction_facts": facts_json,
                    "mapping_results": mapping_json
                }
            )
        return {"test_runs": result}

    finally:
        db.close()


class TestRunReviewRequest(BaseModel):
    decision: str
    review_notes: Optional[str] = None
    update_template_notes: bool = False
    template_notes: Optional[str] = None


@router.post("/templates/{templateId}/test-runs/{testRunId}/review")
async def review_test_run(
    templateId: str,
    testRunId: str,
    payload: TestRunReviewRequest,
    is_admin: bool = Depends(mock_is_admin),
):
    from datetime import datetime

    db = SessionLocal()
    try:
        test_run = (
            db.query(TemplateTestRun)
            .filter(
                TemplateTestRun.id == testRunId,
                TemplateTestRun.template_id == templateId,
            )
            .first()
        )
        if not test_run:
            raise HTTPException(status_code=404, detail="Test run not found")

        test_run.decision = payload.decision
        test_run.review_notes = payload.review_notes
        test_run.reviewed_at = datetime.utcnow()

        if payload.update_template_notes and payload.template_notes:
            template = (
                db.query(TemplateAsset).filter(TemplateAsset.id == templateId).first()
            )
            if template:
                template.notes = payload.template_notes

        db.commit()
        return {"message": "Review saved successfully"}
    finally:
        db.close()


@router.post("/templates/{id}/publish")
async def publish_template(id: str, is_admin: bool = Depends(mock_is_admin)):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        latest_test_run = (
            db.query(TemplateTestRun)
            .filter(TemplateTestRun.template_id == id)
            .order_by(TemplateTestRun.created_at.desc())
            .first()
        )

        validation_result = {}
        if latest_test_run and latest_test_run.validation_result_json:
            validation_result = json.loads(latest_test_run.validation_result_json)

        publish_check = TemplatePublishGuard.can_publish(
            template, latest_test_run, validation_result
        )

        if not publish_check.can_publish:
            raise HTTPException(status_code=400, detail=publish_check.reason)

        template.status = AssetStatus.ACTIVE.value
        db.commit()
        return {"message": f"Template {id} published.", "status": template.status}
    finally:
        db.close()


@router.post("/templates/{id}/archive")
async def archive_template(id: str, is_admin: bool = Depends(mock_is_admin)):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        template.status = AssetStatus.ARCHIVED.value
        db.commit()
        return {"message": f"Template {id} archived.", "status": template.status}
    finally:
        db.close()


@router.post("/templates/{id}/revert-to-draft")
async def revert_to_draft(id: str, is_admin: bool = Depends(mock_is_admin)):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        template.status = AssetStatus.DRAFT.value
        db.commit()
        return {
            "message": f"Template {id} reverted to draft.",
            "status": template.status,
        }
    finally:
        db.close()


@router.post("/knowledge")
async def manage_knowledge():
    return {"message": "Knowledge managed."}


@router.put("/policies/privacy")
async def manage_privacy_policies():
    return {"message": "Privacy policies managed."}


@router.get("/sessions/{id}")
async def inspect_session(id: str):
    return {"session_id": id, "state": "inspected"}


@router.post("/evaluations/run")
async def run_evaluations():
    return {"message": "Evaluations running."}


@router.post("/ranking/rerank")
async def rerank_templates():
    return {"message": "Reranking triggered."}
