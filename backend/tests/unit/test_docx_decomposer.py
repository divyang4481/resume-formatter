from unittest.mock import MagicMock, patch
import pytest

from app.template_analysis.docx_decomposer import decompose_docx
from app.services.template_structure_extractor import TemplateStructure


@patch("app.template_analysis.docx_decomposer.TemplateStructureExtractor")
def test_decompose_docx_with_provided_docling_text(mock_extractor_cls):
    # Setup mock extractor
    mock_extractor = MagicMock()
    mock_extractor_cls.return_value = mock_extractor
    
    # Mock return value of extract
    mock_structure = TemplateStructure()
    mock_structure.doc_lines = ["Line 1", "Line 2"]
    mock_structure.detected_markers = ["«Marker1»"]
    mock_extractor.extract.return_value = mock_structure
    
    # Call decompose_docx with provided docling_text
    evidence = decompose_docx(
        content=b"dummy content",
        docling_text="## Docling Markdown\nSome text"
    )
    
    assert evidence.docling_markdown == "## Docling Markdown\nSome text"
    assert evidence.raw_text_summary == "## Docling Markdown\nSome text"
    assert "«Marker1»" in [p.marker for p in evidence.placeholder_candidates]


@patch("app.template_analysis.docx_decomposer.TemplateStructureExtractor")
@patch("app.template_analysis.docx_decomposer._extract_with_docling_sync")
def test_decompose_docx_without_docling_text_fallback(mock_extract_sync, mock_extractor_cls):
    # Setup mock extractor
    mock_extractor = MagicMock()
    mock_extractor_cls.return_value = mock_extractor
    
    mock_structure = TemplateStructure()
    mock_structure.doc_lines = ["Line 1", "Line 2"]
    mock_extractor.extract.return_value = mock_structure
    
    # Setup mock docling extraction (simulating failure / not installed)
    mock_extract_sync.return_value = None
    
    evidence = decompose_docx(content=b"dummy content")
    
    assert evidence.docling_markdown is None
    assert evidence.raw_text_summary == "Line 1\nLine 2"
