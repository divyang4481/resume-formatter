from abc import ABC, abstractmethod
from typing import Any, Dict, Protocol
from pydantic import BaseModel
from app.schemas.parsed_document import ParsedDocument

class ExtractionContext(BaseModel):
    intent: str
    actor_role: str
    template_id: str | None = None
    template_version: str | None = None
    file_id: str = "unknown"

class ExtractedDocument(BaseModel):
    extracted_text: str
    structured_data: Dict[str, Any] = {}
    backend_used: str
    confidence: float | None = None
    # Add support for the new structured result
    parsed_document: ParsedDocument | None = None
    trace: Any | None = None

class DocumentExtractionService(Protocol):
    async def extract(
        self, file_bytes: bytes, filename: str, content_type: str, context: ExtractionContext
    ) -> ExtractedDocument:
        ...
