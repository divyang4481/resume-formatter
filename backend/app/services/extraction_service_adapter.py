from app.domain.interfaces.document_extraction import DocumentExtractionService, ExtractedDocument, ExtractionContext
from app.services.parser_router import ParserRouter

class RouterBasedExtractionService(DocumentExtractionService):
    """
    Adapts the new ParserRouter to the existing DocumentExtractionService interface.
    """
    def __init__(self):
        self.router = ParserRouter()

    async def extract(
        self, file_bytes: bytes, filename: str, content_type: str, context: ExtractionContext
    ) -> ExtractedDocument:

        parsed_doc, trace = await self.router.route_and_parse(
            file_bytes=file_bytes,
            file_name=filename,
            mime_type=content_type,
            file_id=context.file_id
        )

        return ExtractedDocument(
            extracted_text=parsed_doc.text,
            structured_data=parsed_doc.raw_structured_payload or {},
            backend_used=trace.final_parser_used,
            confidence=trace.final_confidence,
            parsed_document=parsed_doc,
            trace=trace
        )
