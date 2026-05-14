import pytest

from app.adapters.extraction.parser_router import ParserRouter
from app.config import settings
from app.schemas.parsed_document import ParsedDocument, ParsedSection


@pytest.mark.asyncio
async def test_golden_dummy_pdf_routes_through_docling(monkeypatch):
    monkeypatch.setattr(settings, "document_parser_provider", "local_docling")

    async def mock_parse(*args, **kwargs):
        return ParsedDocument(
            text="Golden PDF text " * 30,
            sections=[
                ParsedSection(content="s1"),
                ParsedSection(content="s2"),
                ParsedSection(content="s3"),
            ],
            parser_used="docling",
        )

    monkeypatch.setattr("app.adapters.parsers.docling_parser.DoclingParser.parse", mock_parse)

    result = await ParserRouter().extract(
        b"dummy pdf bytes",
        "golden_clean.pdf",
        "application/pdf",
    )

    assert result.backend_used == "docling"
    assert result.parsed_document is not None
    assert result.parsed_document.parser_used == "docling"
    assert len(result.structured_data["sections"]) == 3
