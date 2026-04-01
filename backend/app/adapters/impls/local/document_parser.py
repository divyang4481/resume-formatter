from app.adapters.base import DocumentParserAdapter
from typing import Dict, Any

class ApacheTikaParser(DocumentParserAdapter):
    """
    Adapter for Local Apache Tika Parser.
    Serves as a fallback or default for unstructured text/PDF.
    """

    def __init__(self):
        # Initialize Tika or other local parsing libraries here
        pass

    def parse(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Parses the document using a local implementation (e.g., Apache Tika).
        """
        return {"backend": "local_tika", "status": "Not Implemented", "extracted_text": ""}

class LocalParser(DocumentParserAdapter):
    """
    Adapter for simple local parsing (e.g. PyPDF2, pdfplumber, docx).
    """

    def __init__(self):
        pass

    def parse(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Parses the document locally.
        """
        return {"backend": "local_parser", "status": "Not Implemented", "extracted_text": ""}
