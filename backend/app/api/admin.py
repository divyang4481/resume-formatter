from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from pydantic import ValidationError
import json
import uuid

from app.schemas.admin import AssetUploadRequestMetadata, AssetUploadResponse
from app.schemas.enums import AssetStatus
from app.dependencies import (
    mock_is_admin,
    storage_provider_dependency,
    template_repository_dependency,
    event_bus_dependency,
    document_extraction_service_dependency,
    get_knowledge_index
)
from app.utils import validate_uploaded_file
from app.services.template_service import TemplateService
from app.domain.interfaces import StorageProvider, TemplateRepository, EventBus, DocumentExtractionService, KnowledgeIndex

router = APIRouter()

@router.post("/templates")
async def push_template():
    return {"message": "Template uploaded."}

@router.post("/templates/upload", response_model=AssetUploadResponse)
async def upload_asset(
    file: UploadFile = File(...),
    metadata: str = Form(..., description="JSON string of AssetUploadRequestMetadata"),
    is_admin: bool = Depends(mock_is_admin),
    storage_provider: StorageProvider = Depends(storage_provider_dependency),
    template_repository: TemplateRepository = Depends(template_repository_dependency),
    event_bus: EventBus = Depends(event_bus_dependency),
    extraction_service: DocumentExtractionService = Depends(document_extraction_service_dependency),
    knowledge_index: KnowledgeIndex = Depends(get_knowledge_index)
):
    try:
        # Validate metadata JSON
        metadata_dict = json.loads(metadata)
        parsed_metadata = AssetUploadRequestMetadata(**metadata_dict)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format in metadata field"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors()
        )

    # Validate file
    await validate_uploaded_file(file)

    # Read the file content bytes
    content = await file.read()

    # Run the template service
    template_service = TemplateService(
        storage_provider=storage_provider,
        template_repository=template_repository,
        event_bus=event_bus,
        extraction_service=extraction_service,
        knowledge_index=knowledge_index
    )

    asset_id = await template_service.upload_asset(
        filename=file.filename,
        content=content,
        metadata=parsed_metadata,
        content_type=file.content_type or "application/octet-stream",
        uploaded_by="admin-user" # placeholder since auth isn't complete yet
    )

    return AssetUploadResponse(
        asset_id=asset_id,
        status=AssetStatus.DRAFT,
        message="Asset uploaded successfully."
    )

@router.get("/templates")
async def pull_templates(
    template_repository: TemplateRepository = Depends(template_repository_dependency),
    is_admin: bool = Depends(mock_is_admin)
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
    selection_weight: Optional[int] = None
    is_default_for_industry: Optional[bool] = None

@router.patch("/templates/{id}")
async def update_template(
    id: str,
    payload: TemplateUpdateRequest,
    is_admin: bool = Depends(mock_is_admin)
):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(template, key, value)

        db.commit()
        return {"message": "Template updated successfully"}
    finally:
        db.close()

@router.get("/templates/{id}")
async def get_template_detail(
    id: str,
    is_admin: bool = Depends(mock_is_admin)
):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        latest_test_run = db.query(TemplateTestRun).filter(
            TemplateTestRun.template_id == id
        ).order_by(TemplateTestRun.created_at.desc()).first()

        validation_result = {}
        if latest_test_run and latest_test_run.validation_result_json:
            validation_result = json.loads(latest_test_run.validation_result_json)

        publish_check = TemplatePublishGuard.can_publish(template, latest_test_run, validation_result)

        return {
            "template": {
                "id": template.id,
                "name": template.name,
                "status": template.status,
                "notes": template.notes,
                "selection_weight": template.selection_weight,
                "industry": template.industry,
                "language": template.language,
                "role_family": template.role_family,
                "updated_at": template.updated_at
            },
            "latest_test_run": {
                "id": latest_test_run.id,
                "decision": latest_test_run.decision,
                "created_at": latest_test_run.created_at
            } if latest_test_run else None,
            "publish_eligibility": {
                "can_publish": publish_check.can_publish,
                "reason": publish_check.reason
            }
        }
    finally:
        db.close()

@router.get("/templates/{id}/test-runs")
async def list_template_test_runs(
    id: str,
    is_admin: bool = Depends(mock_is_admin)
):
    db = SessionLocal()
    try:
        runs = db.query(TemplateTestRun).filter(TemplateTestRun.template_id == id).order_by(TemplateTestRun.created_at.desc()).all()
        import json
        result = []
        for r in runs:
            val_json = {}
            if r.validation_result_json:
                try:
                    val_json = json.loads(r.validation_result_json)
                except Exception:
                    pass
            result.append({
                "id": r.id,
                "job_id": r.processing_job_id,
                "decision": r.decision,
                "created_at": r.created_at,
                "reviewed_at": r.reviewed_at,
                "sample_resume_asset_id": r.sample_resume_asset_id,
                "generated_summary": r.generated_summary,
                "validation_result": val_json
            })
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
    is_admin: bool = Depends(mock_is_admin)
):
    from datetime import datetime
    db = SessionLocal()
    try:
        test_run = db.query(TemplateTestRun).filter(TemplateTestRun.id == testRunId, TemplateTestRun.template_id == templateId).first()
        if not test_run:
            raise HTTPException(status_code=404, detail="Test run not found")

        test_run.decision = payload.decision
        test_run.review_notes = payload.review_notes
        test_run.reviewed_at = datetime.utcnow()

        if payload.update_template_notes and payload.template_notes:
            template = db.query(TemplateAsset).filter(TemplateAsset.id == templateId).first()
            if template:
                template.notes = payload.template_notes

        db.commit()
        return {"message": "Review saved successfully"}
    finally:
        db.close()

@router.post("/templates/{id}/publish")
async def publish_template(
    id: str,
    is_admin: bool = Depends(mock_is_admin)
):
    db = SessionLocal()
    try:
        template = db.query(TemplateAsset).filter(TemplateAsset.id == id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        latest_test_run = db.query(TemplateTestRun).filter(
            TemplateTestRun.template_id == id
        ).order_by(TemplateTestRun.created_at.desc()).first()

        validation_result = {}
        if latest_test_run and latest_test_run.validation_result_json:
            validation_result = json.loads(latest_test_run.validation_result_json)

        publish_check = TemplatePublishGuard.can_publish(template, latest_test_run, validation_result)

        if not publish_check.can_publish:
            raise HTTPException(status_code=400, detail=publish_check.reason)

        template.status = AssetStatus.ACTIVE.value
        db.commit()
        return {"message": f"Template {id} published.", "status": template.status}
    finally:
        db.close()

@router.post("/templates/{id}/archive")
async def archive_template(
    id: str,
    is_admin: bool = Depends(mock_is_admin)
):
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
