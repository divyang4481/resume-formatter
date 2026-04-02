from abc import ABC, abstractmethod
from typing import Any, Dict, List
from app.schemas.parsed_document import ParsedDocument

class DocumentParser(ABC):
    """
    Abstract interface for document extraction engines.
    Ensures that parser choices remain orthogonal to cloud selection.
    """

    @abstractmethod
    async def parse(self, file_bytes: bytes, file_name: str, mime_type: str, options: Dict[str, Any] = None) -> ParsedDocument:
        """
        Parses a document and returns a normalized ParsedDocument.
        """
        ...

    @abstractmethod
    async def healthcheck(self) -> bool:
        """
        Checks if the parser engine is available and ready.
        """
        ...

    @abstractmethod
    def supports(self, mime_type: str, extension: str) -> bool:
        """
        Indicates whether this parser supports the given MIME type and file extension.
        """
        ...

    @abstractmethod
    def capabilities(self) -> List[str]:
        """
        Returns a list of capabilities, e.g., ["ocr", "tables", "sections"].
        """
        ...
