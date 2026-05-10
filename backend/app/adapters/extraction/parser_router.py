import logging
from typing import Dict, Any
from app.domain.interfaces.document_extraction import DocumentExtractionService, ExtractedDocument, ExtractionContext
from app.adapters.parsers.docling_parser import DoclingParser
from app.config import settings

logger = logging.getLogger(__name__)

class ParserRouter(DocumentExtractionService):
    def __init__(self):
        self.docling_parser = DoclingParser()

    async def extract(self, file_bytes: bytes, filename: str, content_type: str, context: ExtractionContext = None) -> ExtractedDocument:
        file_size_mb = len(file_bytes) / (1024 * 1024)
        
        logger.info("Routing to Docling Parser")
        try:
            parsed_doc = await self.docling_parser.parse(file_bytes, filename, content_type)
        except Exception as e:
            logger.error(f"Docling parsing failed: {e}")
            raise Exception(f"Document parsing failed: {e}")

        # Build ExtractedDocument
        text = parsed_doc.text
        sections = [{"title": s.title, "content": s.content} for s in parsed_doc.sections]
        tables = [{"data": t.data} for t in parsed_doc.tables]

        metadata = {
            "parser_used": "docling",
            "file_size_mb": file_size_mb
        }

        return ExtractedDocument(
            extracted_text=text,
            structured_data={"sections": sections, "tables": tables},
            backend_used="docling",
            parsed_document=parsed_doc
        )
