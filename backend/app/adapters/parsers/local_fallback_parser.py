from typing import Dict, Any
from app.domain.interfaces import DocumentExtractionService, ExtractionContext, ExtractedDocument

class ApacheTikaExtractionService(DocumentExtractionService):
    """
    Adapter for Local Apache Tika Parser.
    Serves as a fallback or default for unstructured text/PDF.
    """

    def __init__(self):
        # Initialize Tika or other local parsing libraries here
        pass

    async def extract(self, file_bytes: bytes, filename: str, content_type: str, context: ExtractionContext) -> ExtractedDocument:
        """
        Parses the document using a local implementation (e.g., Apache Tika).
        """
        return ExtractedDocument(
            backend_used="local_tika",
            extracted_text="Sample text extracted via Apache Tika",
            structured_data={"status": "Not Implemented"},
            confidence=0.9
        )

class LocalParserExtractionService(DocumentExtractionService):
    """
    Adapter for simple local parsing (e.g. PyPDF2, pdfplumber, docx).
    """

    def __init__(self):
        pass

    async def extract(self, file_bytes: bytes, filename: str, content_type: str, context: ExtractionContext) -> ExtractedDocument:
        """
        Parses the document locally.
        """
        return ExtractedDocument(
            backend_used="local_parser",
            extracted_text="Sample text extracted via Local Parser",
            structured_data={"status": "Not Implemented"},
            confidence=0.9
        )
