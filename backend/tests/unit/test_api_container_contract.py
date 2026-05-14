from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_api_container_exposes_api_a2a_and_mcp_contracts():
    main_py = (ROOT / "app" / "main.py").read_text()
    a2a_py = (ROOT / "app" / "api" / "a2a.py").read_text()
    dockerfile = (ROOT / "api_backend" / "Dockerfile").read_text()

    assert 'app.include_router(processing_router, prefix="/api/v1/processing"' in main_py
    assert "FastApiMCP(app)" in main_py
    assert "mcp.mount_http()" in main_py
    assert '"/api/capabilities"' in main_py

    assert '"/.well-known/agent-card.json"' in a2a_py
    assert '"/.well-known/agent.json"' in a2a_py
    assert '"/.well-known/mcp.json"' in a2a_py
    assert '"mcp": f"{base_url}/mcp"' in a2a_py

    assert "api_backend.entrypoint:create_app" in dockerfile
    assert "/api/health" in dockerfile


def test_backend_projects_split_heavy_worker_dependencies_from_api():
    api_pyproject = (ROOT / "api_backend" / "pyproject.toml").read_text()
    worker_pyproject = (ROOT / "worker_backend" / "pyproject.toml").read_text()
    common_pyproject = (ROOT / "common" / "pyproject.toml").read_text()
    api_dockerfile = (ROOT / "api_backend" / "Dockerfile").read_text()

    assert 'name = "resume-formatter-common"' in common_pyproject
    assert '"resume-formatter-common==0.1.0"' in api_pyproject
    assert '"resume-formatter-common==0.1.0"' in worker_pyproject
    assert '"docling' not in api_pyproject
    assert '"torch' not in api_pyproject
    assert '"sentence-transformers' not in api_pyproject
    assert '"docling' in worker_pyproject
    assert '"torch' in worker_pyproject
    assert 'COPY ./app ./app' not in api_dockerfile
    assert 'COPY ./app/api ./app/api' in api_dockerfile
