import logging
from typing import Any

from app.config import settings
from app.domain.interfaces.document_extraction import (
    DocumentExtractionService,
    ExtractedDocument,
    ExtractionContext,
)

logger = logging.getLogger(__name__)


class ParserRouter(DocumentExtractionService):
    """Routes extraction to the configured parser backend.

    The default route is the lightweight HTTP parser service so worker images do
    not import Docling/Torch/OCR. A local_docling route is retained for the
    dedicated parser image and developer override scenarios.
    """

    def __init__(self, storage: Any | None = None):
        self.storage = storage
        self._local_docling_parser = None
        self._service_adapter = None

    async def extract(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        context: ExtractionContext | None = None,
    ) -> ExtractedDocument:
        provider = settings.document_parser_provider
        if provider == "docling_service":
            return await self._extract_with_service(file_bytes, filename, content_type, context)
        if provider == "local_docling":
            return await self._extract_with_local_docling(file_bytes, filename, content_type)
        raise ValueError(
            f"Unsupported DOCUMENT_PARSER_PROVIDER={provider!r}. "
            "Expected one of: docling_service, local_docling."
        )

    async def _extract_with_service(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        context: ExtractionContext | None,
    ) -> ExtractedDocument:
        if self._service_adapter is None:
            from app.adapters.extraction.docling_service_adapter import DoclingServiceExtractionAdapter

            self._service_adapter = DoclingServiceExtractionAdapter(storage=self.storage)
        return await self._service_adapter.extract(file_bytes, filename, content_type, context)

    async def _extract_with_local_docling(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> ExtractedDocument:
        if self._local_docling_parser is None:
            from app.adapters.parsers.docling_parser import DoclingParser

            self._local_docling_parser = DoclingParser()

        file_size_mb = len(file_bytes) / (1024 * 1024)
        logger.info("Routing to local Docling parser")
        try:
            parsed_doc = await self._local_docling_parser.parse(file_bytes, filename, content_type)
        except Exception as exc:
            logger.error("Local Docling parsing failed: %s", exc)
            raise Exception(f"Document parsing failed: {exc}") from exc

        sections = [section.model_dump() for section in parsed_doc.sections]
        tables = [table.model_dump() for table in parsed_doc.tables]
        return ExtractedDocument(
            extracted_text=parsed_doc.text,
            structured_data={"sections": sections, "tables": tables},
            backend_used="docling",
            confidence=parsed_doc.confidence,
            parsed_document=parsed_doc,
            trace={"file_size_mb": file_size_mb},
        )
