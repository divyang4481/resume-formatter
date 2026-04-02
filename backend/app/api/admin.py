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

@router.patch("/templates/{id}")
async def update_template(id: str):
    return {"message": "Template updated."}

@router.post("/templates/{id}/publish")
async def publish_template(id: str):
    return {"message": f"Template {id} published."}

@router.post("/templates/{id}/deprecate")
async def deprecate_template(id: str):
    return {"message": f"Template {id} deprecated."}

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
