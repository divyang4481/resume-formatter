from typing import Dict, Any, List

class TemplateDoclingAdapter:
    def __init__(self, extraction_service=None):
        self.extraction_service = extraction_service

    async def extract_text_flow(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Wraps the extraction service to provide text/markdown flow from Docling.
        """
        if not self.extraction_service:
            return {"document_text_flow": []}

        extracted_doc = await self.extraction_service.extract(
            content,
            filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        # In a real implementation this might parse structured text flow
        # Here we just wrap the extracted text
        return {
            "document_text_flow": [extracted_doc.extracted_text] if extracted_doc and extracted_doc.extracted_text else []
        }
