import pytest
from app.services.parser_router import ParserRouter
from app.schemas.parsed_document import ParsedDocument
from app.domain.interfaces.document_parser import DocumentParser

class MockSuccessParser(DocumentParser):
    def __init__(self, confidence=0.9, text="Mock success text"):
        self.conf = confidence
        self.txt = text
        self.used = False

    async def parse(self, file_bytes, file_name, mime_type, options=None):
        self.used = True
        return ParsedDocument(text=self.txt, parser_used="mock_success", confidence=self.conf)

    async def healthcheck(self): return True
    def supports(self, m, e): return True
    def capabilities(self): return []

class MockFailingParser(DocumentParser):
    def __init__(self):
        self.used = False

    async def parse(self, file_bytes, file_name, mime_type, options=None):
        self.used = True
        raise RuntimeError("Mock failure")

    async def healthcheck(self): return True
    def supports(self, m, e): return True
    def capabilities(self): return []

@pytest.fixture
def router():
    return ParserRouter()

@pytest.mark.asyncio
async def test_router_success_primary(router):
    primary = MockSuccessParser(confidence=0.9, text="Primary success")
    fallback = MockSuccessParser(confidence=0.9, text="Fallback success")

    router.parsers["mock_primary"] = primary
    router.parsers["mock_fallback"] = fallback

    # Force the router to use our mocks
    def mock_get_parsers(ext):
        return "mock_primary", "mock_fallback"
    router._get_parsers_for_file = mock_get_parsers

    # We need to mock ParseConfidenceService in route_and_parse, but it's easier to patch the class method
    class MockParseConfidenceService:
        @staticmethod
        def calculate_confidence(parsed_doc):
            return parsed_doc.confidence

    import sys
    sys.modules['app.services.parse_confidence_service'] = type('MockModule', (), {'ParseConfidenceService': MockParseConfidenceService})

    doc, trace = await router.route_and_parse(b"test", "test.pdf", "application/pdf", "file_123")

    # Restore standard module or rely on pytest teardown
    del sys.modules['app.services.parse_confidence_service']

    assert doc.text == "Primary success"
    assert doc.parser_used == "mock_success"
    assert trace.final_parser_used == "mock_primary"
    assert primary.used == True
    assert fallback.used == False
    assert trace.final_confidence == 0.9

@pytest.mark.asyncio
async def test_router_fallback_on_primary_failure(router):
    primary = MockFailingParser()
    fallback = MockSuccessParser(confidence=0.8, text="Fallback success")

    router.parsers["mock_primary"] = primary
    router.parsers["mock_fallback"] = fallback

    router._get_parsers_for_file = lambda ext: ("mock_primary", "mock_fallback")

    class MockParseConfidenceService:
        @staticmethod
        def calculate_confidence(parsed_doc):
            if hasattr(parsed_doc, "confidence") and parsed_doc.confidence is not None:
                return parsed_doc.confidence
            return 0.0

    import sys
    sys.modules['app.services.parse_confidence_service'] = type('MockModule', (), {'ParseConfidenceService': MockParseConfidenceService})

    doc, trace = await router.route_and_parse(b"test", "test.pdf", "application/pdf", "file_123")
    del sys.modules['app.services.parse_confidence_service']

    assert doc.text == "Fallback success"
    assert primary.used == True
    assert fallback.used == True
    assert trace.final_parser_used == "mock_fallback"
    assert len(trace.attempts) == 2
    assert trace.attempts[0].success == False
    assert trace.attempts[1].success == True

@pytest.mark.asyncio
async def test_router_fallback_on_low_confidence(router):
    primary = MockSuccessParser(confidence=0.2, text="Primary low conf")
    fallback = MockSuccessParser(confidence=0.8, text="Fallback success")

    router.parsers["mock_primary"] = primary
    router.parsers["mock_fallback"] = fallback

    router._get_parsers_for_file = lambda ext: ("mock_primary", "mock_fallback")

    class MockParseConfidenceService:
        @staticmethod
        def calculate_confidence(parsed_doc):
            if hasattr(parsed_doc, "confidence") and parsed_doc.confidence is not None:
                return parsed_doc.confidence
            return 0.0

    import sys
    sys.modules['app.services.parse_confidence_service'] = type('MockModule', (), {'ParseConfidenceService': MockParseConfidenceService})

    doc, trace = await router.route_and_parse(b"test", "test.pdf", "application/pdf", "file_123")
    del sys.modules['app.services.parse_confidence_service']

    assert doc.text == "Fallback success"
    assert primary.used == True
    assert fallback.used == True
    assert trace.final_parser_used == "mock_fallback"
