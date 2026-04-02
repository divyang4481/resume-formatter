import pytest
from app.services.parser_router import ParserRouter

# In a real environment, you'd place real simple PDFs and DOCXs here.
# We will use mock bytes but pass them through the router to ensure
# the pipeline handles them as expected based on file extensions.

@pytest.fixture
def router():
    return ParserRouter()

@pytest.mark.asyncio
async def test_golden_dummy_pdf(router, monkeypatch):
    # Mock primary parser to succeed for this golden file test
    async def mock_parse(*args, **kwargs):
        from app.schemas.parsed_document import ParsedDocument, ParsedSection
        return ParsedDocument(
            text="Golden PDF text " * 30, # > 300 chars
            sections=[ParsedSection(content="s1"), ParsedSection(content="s2"), ParsedSection(content="s3")],
            parser_used="docling"
        )

    monkeypatch.setattr(router.parsers["docling"], "parse", mock_parse)

    doc, trace = await router.route_and_parse(b"dummy pdf bytes", "golden_clean.pdf", "application/pdf", "file_1")

    assert doc.parser_used == "docling"
    assert trace.final_confidence == 1.0
    assert len(trace.attempts) == 1
    assert trace.attempts[0].success == True

@pytest.mark.asyncio
async def test_golden_dummy_docx_fallback(router, monkeypatch):
    # Mock primary (docling) to fail to force fallback on a dummy docx
    async def mock_fail(*args, **kwargs):
        raise ValueError("Simulated Docling failure on DOCX")

    async def mock_tika_parse(*args, **kwargs):
        from app.schemas.parsed_document import ParsedDocument
        return ParsedDocument(
            text="Recovered text by Tika " * 20,
            parser_used="tika"
        )

    monkeypatch.setattr(router.parsers["docling"], "parse", mock_fail)
    monkeypatch.setattr(router.parsers["tika"], "parse", mock_tika_parse)

    doc, trace = await router.route_and_parse(b"dummy docx bytes", "golden_table.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "file_2")

    assert doc.parser_used == "tika"
    assert trace.final_parser_used == "tika"
    assert trace.warnings # Should contain a warning about fallback
    assert trace.attempts[0].success == False
    assert trace.attempts[1].success == True
