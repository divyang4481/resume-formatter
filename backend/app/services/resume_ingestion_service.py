from typing import Optional
from app.domain.interfaces import DocumentExtractionService, ExtractionContext
import os

class ResumeIngestionService:
    def __init__(self, extractor: DocumentExtractionService):
        self.extractor = extractor

    async def ingest(self, file_bytes: bytes, filename: str, content_type: str, context: ExtractionContext):
        # Always extract for any resume
        extracted = await self.extractor.extract(
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type,
            context=context
        )

        if context.intent == "candidate_runtime":
            return await self._process_candidate_resume(extracted, context)

        if context.intent == "admin_sample_resume":
            return await self._process_sample_resume(extracted, context)

        raise ValueError(f"Unsupported processing intent: {context.intent}")

    async def _process_candidate_resume(self, extracted, context: ExtractionContext):
        # Specific logic for candidate resumes
        return {
            "status": "candidate_resume_processed",
            "extracted_text": extracted.extracted_text,
            "structured_data": extracted.structured_data,
            "backend_used": extracted.backend_used
        }


    async def _process_sample_resume(self, extracted, context: ExtractionContext):
        # Specific logic for admin sample resumes (e.g., skip rendering, add richer diagnostics)
        return {
            "status": "sample_resume_processed",
            "extracted_text": extracted.extracted_text,
            "structured_data": extracted.structured_data,
            "backend_used": extracted.backend_used
        }

