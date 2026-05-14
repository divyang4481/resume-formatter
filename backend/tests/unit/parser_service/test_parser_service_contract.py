from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_worker_routes_to_parser_service_without_heavy_runtime_dependencies():
    worker_pyproject = (ROOT / "worker_backend" / "pyproject.toml").read_text()
    worker_dockerfile = (ROOT / "worker_backend" / "Dockerfile").read_text()
    router = (ROOT / "app" / "adapters" / "extraction" / "parser_router.py").read_text()

    assert '"docling' not in worker_pyproject
    assert '"torch' not in worker_pyproject
    assert "rapidocr" not in worker_dockerfile.lower()
    assert "DoclingServiceExtractionAdapter" in router
    assert "from app.adapters.parsers.docling_parser import DoclingParser" not in router.split("\n", 12)[:12]


def test_parser_docling_service_has_own_image_and_compose_service():
    compose = (ROOT.parent / "docker-compose.yml").read_text()
    parser_pyproject = (ROOT / "parser_service" / "pyproject.toml").read_text()
    parser_main = (ROOT / "parser_service" / "app" / "main.py").read_text()

    assert "parser-docling:" in compose
    assert "parser_service/Dockerfile" in compose
    assert '"docling' in parser_pyproject
    assert '"torch' in parser_pyproject
    assert '@app.post("/parse-document"' in parser_main
