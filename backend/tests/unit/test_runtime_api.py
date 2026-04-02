from fastapi.testclient import TestClient
from app.main import app
import os

client = TestClient(app)

def test_submit_document_valid():
    # Create a dummy file
    file_content = b"dummy content"
    files = {"file": ("test.pdf", file_content, "application/pdf")}
    response = client.post("/v1/runtime/documents/submit", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert "document_id" in data
    assert data["status"] == "waiting_for_confirmation"
    assert data["requires_confirmation"] is True
    assert data["suggested_industry_id"] == "it"

def test_submit_document_invalid_extension():
    file_content = b"dummy content"
    files = {"file": ("test.exe", file_content, "application/x-msdownload")}
    response = client.post("/v1/runtime/documents/submit", files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_get_job_status():
    file_content = b"dummy content"
    files = {"file": ("test.pdf", file_content, "application/pdf")}
    submit_response = client.post("/v1/runtime/documents/submit", files=files)
    job_id = submit_response.json()["job_id"]

    response = client.get(f"/v1/runtime/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "waiting_for_confirmation"
