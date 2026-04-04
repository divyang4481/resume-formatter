import logging
from app.domain.interfaces.document_extraction import DocumentExtractionService, ExtractedDocument, ExtractionContext
from .parser_router import ParserRouter

logger = logging.getLogger(__name__)

class RouterExtractionService(DocumentExtractionService):
    """
    Adapts the new ParserRouter to the existing DocumentExtractionService interface.
    """
    def __init__(self):
        self.router = ParserRouter()

    async def extract(
        self, file_bytes: bytes, filename: str, content_type: str, context: ExtractionContext
    ) -> ExtractedDocument:
        logger.info(f"Starting extraction for file: '{filename}', content_type: '{content_type}', file_id: '{context.file_id}'")
        try:
            parsed_doc, trace = await self.router.route_and_parse(
                file_bytes=file_bytes,
                file_name=filename,
                mime_type=content_type,
                file_id=context.file_id
            )

            extracted_text = parsed_doc.text
            text_length = len(extracted_text) if extracted_text else 0

            logger.info(
                f"Extraction successful for file: '{filename}'. "
                f"Backend used: '{trace.final_parser_used}', Confidence: {trace.final_confidence}, "
                f"Extracted text length: {text_length} characters."
            )
            logger.debug(f"Extraction trace details: {trace}")
            if text_length > 0:
                logger.debug(f"Extracted text excerpt for '{filename}':\n{extracted_text[:1000]}")

            return ExtractedDocument(
                extracted_text=extracted_text,
                structured_data=parsed_doc.raw_structured_payload or {},
                backend_used=trace.final_parser_used,
                confidence=trace.final_confidence,
                parsed_document=parsed_doc,
                trace=trace
            )
        except Exception as e:
            logger.error(f"Failed to extract document '{filename}': {e}", exc_info=True)
            raise
