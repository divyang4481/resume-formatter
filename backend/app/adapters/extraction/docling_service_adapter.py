import json
import logging
import uuid
from typing import Any

import httpx

from app.config import settings
from app.domain.interfaces.document_extraction import (
    DocumentExtractionService,
    ExtractedDocument,
    ExtractionContext,
)
from app.schemas.parsed_document import ParsedDocument

logger = logging.getLogger(__name__)


class DoclingServiceExtractionAdapter(DocumentExtractionService):
    """Thin worker-side adapter for the dedicated Docling parser service.

    The worker remains responsible for orchestration and cloud adapters, while
    the heavy parser container owns Docling/Torch/OCR imports and execution.
    """

    def __init__(self, storage: Any | None = None, service_url: str | None = None):
        from app.dependencies import get_storage_provider

        self.storage = storage or get_storage_provider()
        self.service_url = (service_url or settings.parser_service_url).rstrip("/")
        self.timeout_seconds = settings.parser_timeout_seconds

    async def extract(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        context: ExtractionContext | None = None,
    ) -> ExtractedDocument:
        context = context or ExtractionContext(intent="candidate_runtime", actor_role="system")
        job_id = context.file_id if context.file_id != "unknown" else str(uuid.uuid4())
        safe_filename = filename.rsplit("/", 1)[-1] or "document"
        input_key = f"parser-service/{job_id}/input/{safe_filename}"
        output_key = f"parser-service/{job_id}/parsed.json"

        input_uri = self.storage.put_bytes(file_bytes, input_key, content_type)
        output_uri = self.storage.put_bytes(b"{}", output_key, "application/json")

        payload = {
            "job_id": job_id,
            "input_uri": input_uri,
            "output_uri": output_uri,
            "parser_profile": "resume_v1",
            "requested_outputs": ["text", "sections", "tables", "layout_blocks"],
        }

        logger.info("Requesting document parse from %s for %s", self.service_url, filename)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.service_url}/parse-document", json=payload)
            response.raise_for_status()
            metadata = response.json()

        parsed_uri = metadata.get("output_uri", output_uri)
        parsed_payload = json.loads(self.storage.get_bytes(parsed_uri).decode("utf-8"))
        parsed_doc = ParsedDocument.model_validate(parsed_payload)

        sections = [section.model_dump() for section in parsed_doc.sections]
        tables = [table.model_dump() for table in parsed_doc.tables]
        return ExtractedDocument(
            extracted_text=parsed_doc.text,
            structured_data={"sections": sections, "tables": tables},
            backend_used=metadata.get("parser_used", parsed_doc.parser_used or "docling_service"),
            confidence=parsed_doc.confidence,
            parsed_document=parsed_doc,
            trace={"parser_service": self.service_url, "output_uri": parsed_uri},
        )
