import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.enums import ExecutionMode
from app.schemas.runtime import SubmitDocumentResponse
from app.db.session import SessionLocal
from app.db.models import TemplateAsset, TemplateTestRun
import uuid
import json

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup - handled by lifespan usually but for TestClient sometimes we need explicit init
    from app.db.session import engine
    from app.db.models import Base
    Base.metadata.create_all(bind=engine)

    yield

    # Teardown
    db = SessionLocal()
    db.query(TemplateTestRun).delete()
    db.query(TemplateAsset).delete()
    db.commit()
    db.close()

def test_admin_pipeline_flow():
    # 1. Admin uploads a template
    template_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        new_template = TemplateAsset(
            id=template_id,
            version="1.0",
            name="Test Mock Template",
            language="en",
            status="draft",
            created_by="admin"
        )
        db.add(new_template)
        db.commit()
    finally:
        db.close()

    # 2. Test fetching the template detail
    response = client.get(
        f"/admin/templates/{template_id}",
        headers={"X-Admin-Token": "admin-secret-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["template"]["name"] == "Test Mock Template"
    assert data["publish_eligibility"]["can_publish"] == False # No test runs yet

    # 3. Admin submits a sample resume using admin_template_test mode
    sample_content = b"Sample resume for John Doe, Software Engineer."
    response = client.post(
        "/v1/processing/documents/submit",
        headers={
            "X-Execution-Mode": ExecutionMode.ADMIN_TEMPLATE_TEST.value,
            "X-Actor-Role": "admin"
        },
        data={"template_id": template_id, "industry_id": "it"},
        files={"file": ("sample.pdf", sample_content, "application/pdf")}
    )
    assert response.status_code == 200
    submit_data = response.json()
    job_id = submit_data["job_id"]

    # 4. Verify TemplateTestRun is created
    db = SessionLocal()
    try:
        test_run = db.query(TemplateTestRun).filter(TemplateTestRun.processing_job_id == job_id).first()
        assert test_run is not None
        assert test_run.template_id == template_id
        test_run_id = test_run.id
    finally:
        db.close()

    # 5. Mock a passing validation and decision in the test run
    review_payload = {
        "decision": "PASS",
        "review_notes": "Looks good",
        "update_template_notes": True,
        "template_notes": "Focus on backend skills"
    }

    response = client.post(
        f"/admin/templates/{template_id}/test-runs/{test_run_id}/review",
        json=review_payload,
        headers={"X-Admin-Token": "admin-secret-token"}
    )
    assert response.status_code == 200

    # 6. Verify template is now eligible and publish it
    response = client.post(
        f"/admin/templates/{template_id}/publish",
        headers={"X-Admin-Token": "admin-secret-token"}
    )
    assert response.status_code == 200

    # 7. Verify status changed to ACTIVE
    response = client.get(
        f"/admin/templates/{template_id}",
        headers={"X-Admin-Token": "admin-secret-token"}
    )
    data = response.json()
    assert data["template"]["status"] == "active"
    assert data["template"]["notes"] == "Focus on backend skills"
