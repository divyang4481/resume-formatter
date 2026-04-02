import pytest
from fastapi.testclient import TestClient
import json
from app.main import app

client = TestClient(app)

def test_upload_asset_success():
    # Valid metadata and file
    metadata = {
        "asset_type": "template",
        "name": "Test Template"
    }
    file_content = b"Mock PDF Content"

    response = client.post(
        "/admin/templates/upload",
        headers={"X-Admin-Token": "admin-secret-token"},
        data={"metadata": json.dumps(metadata)},
        files={"file": ("test.pdf", file_content, "application/pdf")}
    )

    assert response.status_code == 200
    data = response.json()
    assert "asset_id" in data
    assert data["status"] == "draft"

def test_upload_asset_unauthorized():
    # Missing admin token
    response = client.post(
        "/admin/templates/upload",
        data={"metadata": "{}"},
        files={"file": ("test.pdf", b"test", "application/pdf")}
    )
    assert response.status_code == 403

def test_upload_asset_invalid_metadata():
    response = client.post(
        "/admin/templates/upload",
        headers={"X-Admin-Token": "admin-secret-token"},
        data={"metadata": "invalid json"},
        files={"file": ("test.pdf", b"test", "application/pdf")}
    )
    assert response.status_code == 400

def test_upload_asset_missing_metadata_fields():
    metadata = {"name": "Missing type"}
    response = client.post(
        "/admin/templates/upload",
        headers={"X-Admin-Token": "admin-secret-token"},
        data={"metadata": json.dumps(metadata)},
        files={"file": ("test.pdf", b"test", "application/pdf")}
    )
    assert response.status_code == 422

def test_upload_asset_invalid_file_extension():
    metadata = {
        "asset_type": "template",
        "name": "Test Template"
    }
    response = client.post(
        "/admin/templates/upload",
        headers={"X-Admin-Token": "admin-secret-token"},
        data={"metadata": json.dumps(metadata)},
        files={"file": ("test.exe", b"test", "application/x-msdownload")}
    )
    assert response.status_code == 415

def test_upload_asset_empty_file():
    metadata = {
        "asset_type": "template",
        "name": "Test Template"
    }
    response = client.post(
        "/admin/templates/upload",
        headers={"X-Admin-Token": "admin-secret-token"},
        data={"metadata": json.dumps(metadata)},
        files={"file": ("test.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400


def test_pull_templates_success():
    response = client.get(
        "/admin/templates",
        headers={"X-Admin-Token": "admin-secret-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "templates" in data
    assert isinstance(data["templates"], list)

def test_pull_templates_unauthorized():
    response = client.get(
        "/admin/templates"
    )
    assert response.status_code == 403
