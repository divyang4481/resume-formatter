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
