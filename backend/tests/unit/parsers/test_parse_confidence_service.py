from app.services.parse_confidence_service import ParseConfidenceService
from app.schemas.parsed_document import ParsedDocument, ParsedSection
from app.config import settings

def test_confidence_zero_text():
    doc = ParsedDocument(text="")
    assert ParseConfidenceService.calculate_confidence(doc) == 0.0

def test_confidence_low_text_length():
    # settings.parser_min_text_chars defaults to 300
    doc = ParsedDocument(text="A short text")
    # Base 1.0 - 0.5 (low text) = 0.5
    assert ParseConfidenceService.calculate_confidence(doc) == 0.5

def test_confidence_docling_good_structure():
    doc = ParsedDocument(
        text="A" * 350,
        parser_used="docling",
        sections=[ParsedSection(content="s1"), ParsedSection(content="s2"), ParsedSection(content="s3"), ParsedSection(content="s4")]
    )
    # text >= 300 -> 1.0. sections >= 3 -> 1.0
    assert ParseConfidenceService.calculate_confidence(doc) == 1.0

def test_confidence_docling_poor_structure():
    doc = ParsedDocument(
        text="A" * 350,
        parser_used="docling",
        sections=[ParsedSection(content="s1")]
    )
    # sections < 3 (penalty -0.3)
    # Base 1.0 - 0.3 = 0.7
    assert round(ParseConfidenceService.calculate_confidence(doc), 1) == 0.7

def test_confidence_tika_cap():
    doc = ParsedDocument(
        text="A" * 350,
        parser_used="tika"
    )
    # Tika is capped at 0.8
    assert ParseConfidenceService.calculate_confidence(doc) == 0.8
