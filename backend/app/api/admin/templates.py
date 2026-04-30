from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from typing import Optional, List
import uuid

from app.dependencies import get_document_extraction_service, get_llm_runtime
import json
import logging

logger = logging.getLogger(__name__)

def parse_llm_json(response: str) -> list:
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        return json.loads(response.strip())
    except Exception as e:
        logger.error(f"Failed to parse LLM JSON: {e}")
        return []


from app.dependencies import mock_is_admin, get_template_repository, get_job_repository, get_storage_provider, get_message_queue
from app.db.models import TemplateAsset, TemplateKnowledgeBinding, ProcessingJob

router = APIRouter(dependencies=[Depends(mock_is_admin)])

@router.post("/templates")
async def create_draft_template(name: str = Form(...), industry: str = Form(None), template_repo = Depends(get_template_repository)):
    """Creates a new draft template."""
    template_id = str(uuid.uuid4())
    draft_template = TemplateAsset(
        id=template_id,
        name=name,
        version="1.0.0",
        status="DRAFT",
        industry=industry,
        created_by="admin_user",
        is_active=False
    )
    template_repo.db.add(draft_template)
    template_repo.db.commit()
    return {"template_id": template_id, "status": "DRAFT", "version": "1.0.0"}


@router.post("/templates/{template_id}/versions/{version_id}/upload-template")
async def upload_template_docx(
    template_id: str,
    version_id: str,
    file: UploadFile = File(...),
    storage = Depends(get_storage_provider),
    template_repo = Depends(get_template_repository),
    job_repo = Depends(get_job_repository),
    queue = Depends(get_message_queue)
):
    """Uploads DOCX and enqueues a TEMPLATE_PROCESSING job to infer contract dynamically via Agentic Core."""
    template = template_repo.db.query(TemplateAsset).filter_by(id=template_id, version=version_id).first()
    if not template or template.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Can only upload to DRAFT templates.")

    file_bytes = await file.read()
    key = f"admin/templates/{template_id}/{version_id}/{file.filename}"
    uri = storage.put_bytes(file_bytes, key, file.content_type)

    template.storage_uri = uri
    template.file_name = file.filename
    template_repo.db.commit()

    job_id = str(uuid.uuid4())
    job = ProcessingJob(
        id=job_id,
        candidate_resume_id=None,
        original_file_ref=uri,
        template_asset_id=template_id,
        template_version=version_id,
        status="PROCESSING",
        stage="init",
        job_type="TEMPLATE_PROCESSING"
    )
    job_repo.db.add(job)
    job_repo.db.commit()

    queue.publish({
        "job_id": job_id,
        "job_type": "TEMPLATE_PROCESSING",
        "input_uri": uri,
        "template_id": template_id,
        "version_id": version_id
    })

    return {
        "template_id": template_id,
        "version_id": version_id,
        "job_id": job_id,
        "status": "PROCESSING",
        "contract_status": "PROCESSING",
        "template_contract": None,
        "message": "Template uploaded. Contract generation is running in background."
    }

@router.get("/templates/{template_id}/versions/{version_id}")
async def get_template_version(
    template_id: str,
    version_id: str,
    template_repo = Depends(get_template_repository)
):
    """Fetches a template version with its generated contract if available."""
    template = template_repo.db.query(TemplateAsset).filter_by(id=template_id, version=version_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    manifest = []
    if template.field_extraction_manifest:
        try:
            manifest = json.loads(template.field_extraction_manifest)
        except:
            pass

    return {
        "template_id": template.id,
        "version_id": template.version,
        "status": template.status,
        "contract_status": "COMPLETED" if template.field_extraction_manifest else "PROCESSING",
        "template_contract": {
            "fields": template.expected_fields.split(",") if template.expected_fields else [],
            "sections": template.expected_sections.split(",") if template.expected_sections else [],
            "manifest": manifest
        }
    }


@router.post("/templates/{template_id}/versions/{version_id}/kb/assets")
async def add_kb_asset(
    template_id: str,
    version_id: str,
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    storage = Depends(get_storage_provider)
):
    """Adds a KB asset (e.g. policy doc) to a template version."""
    file_bytes = await file.read()
    key = f"admin/templates/{template_id}/{version_id}/kb/{file.filename}"
    uri = storage.put_bytes(file_bytes, key, file.content_type)
    return {"status": "success", "asset_uri": uri, "asset_type": asset_type}

@router.post("/templates/{template_id}/versions/{version_id}/prompt-policy")
async def configure_prompt_policy(template_id: str, version_id: str, policy: dict):
    """Configures prompt policy for a template version."""
    return {"status": "success", "message": "Prompt policy saved (mocked)"}

@router.post("/templates/{template_id}/versions/{version_id}/test-runs")
async def create_test_run(
    template_id: str,
    version_id: str,
    file: UploadFile = File(...),
    storage = Depends(get_storage_provider),
    job_repo = Depends(get_job_repository),
    queue = Depends(get_message_queue)
):
    """Tests the template with a sample resume."""
    file_bytes = await file.read()
    key = f"admin/templates/{template_id}/{version_id}/test-runs/{file.filename}"
    uri = storage.put_bytes(file_bytes, key, file.content_type)

    job_id = str(uuid.uuid4())
    job = ProcessingJob(
        id=job_id,
        candidate_resume_id=None,
        original_file_ref=uri,
        template_asset_id=template_id,
        template_version=version_id,
        status="QUEUED",
        stage="init",
        job_type="TEMPLATE_TEST_RUN"
    )
    job_repo.db.add(job)
    job_repo.db.commit()

    queue.publish({"job_id": job_id, "job_type": "TEMPLATE_TEST_RUN", "input_uri": uri})

    return {"test_run_id": job_id, "status": "QUEUED"}

@router.post("/templates/{template_id}/versions/{version_id}/publish")
async def publish_template(
    template_id: str,
    version_id: str,
    template_repo = Depends(get_template_repository)
):
    """Publishes a tested template."""
    template = template_repo.db.query(TemplateAsset).filter_by(id=template_id, version=version_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    template.status = "PUBLISHED"
    template.is_active = True
    template_repo.db.commit()
    return {"status": "success", "message": "Template published and active."}

@router.post("/templates/{template_id}/versions/{version_id}/deactivate")
async def deactivate_template(
    template_id: str,
    version_id: str,
    template_repo = Depends(get_template_repository)
):
    """Deactivates a published template."""
    template = template_repo.db.query(TemplateAsset).filter_by(id=template_id, version=version_id).first()
    if template:
        template.is_active = False
        template_repo.db.commit()
    return {"status": "success"}
