import pytest
from app.adapters.parsers.docling_parser import DoclingParser
from app.schemas.parsed_document import ParsedDocument

# We will skip docling contract test in CI if docling isn't fully installed or requires real PDFs
# But it ensures the contract is maintained if we mock the converter.
@pytest.mark.asyncio
async def test_docling_parser_contract(monkeypatch):
    parser = DoclingParser()

    # Mock docling inner logic for contract test
    class MockDoclingItem:
        def __init__(self, label, text):
            self.label = label
            self.text = text

    class MockDoc:
        def iterate_items(self):
            yield MockDoclingItem("paragraph", "Hello from docling"), 1
        def export_to_markdown(self):
            return "Hello from docling markdown"

    class MockResult:
        @property
        def document(self):
            return MockDoc()

    def mock_convert(*args, **kwargs):
        return MockResult()

    if parser.converter is not None:
        monkeypatch.setattr(parser.converter, "convert", mock_convert)
        doc = await parser.parse(b"dummy pdf bytes", "test.pdf", "application/pdf")

        assert isinstance(doc, ParsedDocument)
        assert doc.parser_used == "docling"
        assert "Hello from docling markdown" in doc.text

@pytest.mark.asyncio
async def test_docling_parser_graceful_fallback():
    parser = DoclingParser()
    
    # Passing invalid dummy bytes triggers the native exception and plain text fallback
    doc = await parser.parse(b"dummy pdf bytes containing some clear text content", "test.pdf", "application/pdf")
    
    assert isinstance(doc, ParsedDocument)
    assert doc.parser_used == "docling-fallback-text"
    assert "dummy pdf bytes containing some clear text content" in doc.text
    assert "parsing_error" in doc.metadata
    assert len(doc.sections) == 1
    assert doc.sections[0].title == "Extracted Content"
    assert doc.sections[0].content == "dummy pdf bytes containing some clear text content"
