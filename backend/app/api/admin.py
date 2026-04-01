from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from pydantic import ValidationError
import json
import uuid

from app.schemas.admin import AssetUploadRequestMetadata, AssetUploadResponse
from app.schemas.enums import AssetStatus
from app.dependencies import mock_is_admin
from app.utils import validate_uploaded_file

router = APIRouter()

@router.post("/templates")
async def push_template():
    return {"message": "Template uploaded."}

@router.post("/templates/upload", response_model=AssetUploadResponse)
async def upload_asset(
    file: UploadFile = File(...),
    metadata: str = Form(..., description="JSON string of AssetUploadRequestMetadata"),
    is_admin: bool = Depends(mock_is_admin)
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

    # Simulate generating an ID and processing the file
    asset_id = str(uuid.uuid4())

    return AssetUploadResponse(
        asset_id=asset_id,
        status=AssetStatus.DRAFT,
        message="Asset uploaded successfully."
    )

@router.get("/templates")
async def pull_templates():
    return {"templates": []}

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
