import logging
from typing import Dict, Any
from app.domain.interfaces.document_extraction import DocumentExtractionService, ExtractedDocument, ExtractionContext
from app.adapters.parsers.docling_parser import DoclingParser
from app.adapters.parsers.tika_parser import TikaParser
from app.config import settings

logger = logging.getLogger(__name__)

class ParserRouter(DocumentExtractionService):
    def __init__(self):
        self.docling_parser = DoclingParser() if settings.enable_docling else None
        self.tika_parser = TikaParser() if settings.enable_tika_fallback else None

    async def extract(self, file_bytes: bytes, filename: str, content_type: str, context: ExtractionContext = None) -> ExtractedDocument:
        file_size_mb = len(file_bytes) / (1024 * 1024)
        is_docx = filename.lower().endswith(".docx")
        is_pdf = filename.lower().endswith(".pdf")

        # Simple heuristic parser routing guard
        use_docling = False
        if settings.enable_docling:
            if is_docx:
                use_docling = True # Enable Docling for .docx as requested
            if is_pdf:
                # If we have a PDF and docling is enabled, use it
                use_docling = True

        parser_used = "tika"
        needs_ocr = False
        gpu_recommended = False
        parsed_doc = None

        if use_docling and self.docling_parser:
            logger.info("Routing to Docling Parser")
            try:
                parsed_doc = await self.docling_parser.parse(file_bytes, filename, content_type)
                parser_used = "docling"
                if file_size_mb > 2:
                    needs_ocr = True
                    gpu_recommended = True
            except Exception as e:
                logger.warning(f"Docling failed, falling back: {e}")

        if not parsed_doc and self.tika_parser:
            logger.info("Routing to Tika Parser")
            parsed_doc = await self.tika_parser.parse(file_bytes, filename, content_type)
            parser_used = "tika"

        if not parsed_doc:
            raise Exception("All parsers failed or none configured.")

        # Build ExtractedDocument
        text = parsed_doc.text
        sections = [{"title": s.title, "content": s.content} for s in parsed_doc.sections]
        tables = [{"data": t.data} for t in parsed_doc.tables]

        metadata = {
            "parser_used": parser_used,
            "needs_ocr": needs_ocr,
            "gpu_recommended": gpu_recommended,
            "file_size_mb": file_size_mb
        }

        return ExtractedDocument(
            extracted_text=text,
            structured_data={"sections": sections, "tables": tables},
            backend_used=parser_used,
            parsed_document=parsed_doc
        )
