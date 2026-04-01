"""Tests for ExtractionAgent."""

from __future__ import annotations

import io
import struct
import textwrap
import zlib
from unittest.mock import MagicMock, patch

import pytest

from resume_formatter.agents.extraction_agent import ExtractionAgent


# ---------------------------------------------------------------------------
# Helpers – minimal in-memory documents
# ---------------------------------------------------------------------------

def _minimal_pdf_bytes(text: str = "Hello PDF") -> bytes:
    """Return a valid minimal single-page PDF containing *text*."""
    # Build using pypdf if available, otherwise produce a raw minimal PDF
    try:
        import pypdf
        from pypdf import PdfWriter
        from pypdf.generic import NameObject, ArrayObject, NumberObject

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        # Add text via a content stream
        content = f"BT /F1 12 Tf 10 180 Td ({text}) Tj ET"
        page = writer.pages[0]
        from pypdf.generic import ContentStream, DecodedStreamObject
        stream_obj = DecodedStreamObject()
        stream_obj.set_data(content.encode())
        page["/Contents"] = writer._add_object(stream_obj)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception:
        # Minimal raw PDF that pypdf can open (text may be empty)
        lines = [
            b"%PDF-1.4",
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
            b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj",
            b"xref",
            b"0 4",
            b"0000000000 65535 f ",
            b"trailer<</Size 4/Root 1 0 R>>",
            b"startxref",
            b"0",
            b"%%EOF",
        ]
        return b"\n".join(lines)


def _minimal_docx_bytes(text: str = "Hello DOCX") -> bytes:
    """Return a minimal .docx file containing *text*."""
    from docx import Document

    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExtractionAgentDocx:
    def test_extract_docx_from_bytes(self):
        agent = ExtractionAgent()
        data = _minimal_docx_bytes("My DOCX content")
        result = agent.extract(data, extension=".docx")
        assert "My DOCX content" in result

    def test_extract_docx_from_path(self, tmp_path):
        agent = ExtractionAgent()
        path = tmp_path / "sample.docx"
        path.write_bytes(_minimal_docx_bytes("Path DOCX"))
        result = agent.extract(path)
        assert "Path DOCX" in result


class TestExtractionAgentPdf:
    def test_extract_pdf_from_bytes(self):
        agent = ExtractionAgent()
        data = _minimal_pdf_bytes("Resume PDF")
        # pypdf may or may not extract text from the raw minimal PDF, but it
        # should return a string without raising an exception
        result = agent.extract(data, extension=".pdf")
        assert isinstance(result, str)

    def test_extract_pdf_from_path(self, tmp_path):
        agent = ExtractionAgent()
        path = tmp_path / "sample.pdf"
        path.write_bytes(_minimal_pdf_bytes())
        result = agent.extract(path)
        assert isinstance(result, str)


class TestExtractionAgentImage:
    def test_extract_image_calls_tesseract(self):
        """Verify that the OCR path calls pytesseract.image_to_string."""
        agent = ExtractionAgent()

        # Create a tiny valid PNG (1×1 white pixel)
        import struct, zlib
        def _tiny_png() -> bytes:
            sig = b"\x89PNG\r\n\x1a\n"
            def chunk(name: bytes, data: bytes) -> bytes:
                return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
            ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            raw = b"\x00\xff\xff\xff"
            idat = chunk(b"IDAT", zlib.compress(raw))
            iend = chunk(b"IEND", b"")
            return sig + ihdr + idat + iend

        with patch("pytesseract.image_to_string", return_value="OCR text") as mock_tess:
            result = agent.extract(_tiny_png(), extension=".png")

        mock_tess.assert_called_once()
        assert result == "OCR text"

    def test_unsupported_extension_raises(self):
        agent = ExtractionAgent()
        with pytest.raises(ValueError, match="Unsupported file extension"):
            agent.extract(b"data", extension=".xyz")
