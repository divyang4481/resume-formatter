from typing import Any, Dict, List
from app.domain.interfaces.document_parser import DocumentParser
from app.schemas.parsed_document import ParsedDocument

class AzureDocumentIntelligenceParser(DocumentParser):
    """
    Stub implementation for Azure Document Intelligence.
    To be fully implemented in a later phase.
    """
    def __init__(self):
        pass

    async def parse(self, file_bytes: bytes, file_name: str, mime_type: str, options: Dict[str, Any] = None) -> ParsedDocument:
        raise NotImplementedError("Azure Document Intelligence parser is not fully implemented yet.")

    async def healthcheck(self) -> bool:
        # Stub check
        return False

    def supports(self, mime_type: str, extension: str) -> bool:
        return extension.lower() in [".pdf", ".jpeg", ".jpg", ".png", ".tiff", ".bmp", ".docx"]

    def capabilities(self) -> List[str]:
        return ["ocr", "layout", "tables", "key-value"]
