import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_upload_creates_waiting_job():
    response = client.post(
        "/runtime/resumes/upload",
        files={"file": ("test_resume.pdf", b"dummy content", "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "WAITING_FOR_CONFIRMATION"
    assert "file_uri" in data

def test_confirm_publishes_queue_message():
    # 1. Upload
    res = client.post(
        "/runtime/resumes/upload",
        files={"file": ("test_resume.pdf", b"dummy content", "application/pdf")}
    )
    job_id = res.json()["job_id"]

    # 2. Confirm
    confirm_res = client.post(f"/runtime/resumes/{job_id}/confirm")
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "QUEUED"

def test_admin_create_draft_template():
    response = client.post(
        "/admin/templates",
        data={"name": "Test Template", "industry": "Tech"},
        headers={"X-Admin-Token": "secret-admin-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "template_id" in data
    assert data["status"] == "DRAFT"

def test_admin_test_run():
    # 1. Create draft
    draft_res = client.post(
        "/admin/templates",
        data={"name": "Test Template", "industry": "Tech"},
        headers={"X-Admin-Token": "secret-admin-token"}
    )
    template_id = draft_res.json()["template_id"]
    version_id = draft_res.json()["version"]

    # 2. Upload template to generate contract
    client.post(
        f"/admin/templates/{template_id}/versions/{version_id}/upload-template",
        files={"file": ("template.docx", b"dummy", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers={"X-Admin-Token": "secret-admin-token"}
    )

    # 3. Create test run
    test_run_res = client.post(
        f"/admin/templates/{template_id}/versions/{version_id}/test-runs",
        files={"file": ("sample_cv.pdf", b"dummy pdf", "application/pdf")},
        headers={"X-Admin-Token": "secret-admin-token"}
    )
    assert test_run_res.status_code == 200
    data = test_run_res.json()
    assert "test_run_id" in data
    assert data["status"] == "QUEUED"
