import io
import os
import tempfile
from typing import Any, Dict, List
from docling.document_converter import DocumentConverter
from app.domain.interfaces.document_parser import DocumentParser
from app.schemas.parsed_document import ParsedDocument, ParsedSection, ParsedTable

class DoclingParser(DocumentParser):
    def __init__(self):
        self.converter = DocumentConverter()

    async def parse(self, file_bytes: bytes, file_name: str, mime_type: str, options: Dict[str, Any] = None) -> ParsedDocument:
        # Docling primarily works with files on disk, so we use a temp file
        ext = os.path.splitext(file_name)[1]
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            # Note: Docling processing is CPU bound, might want to run in an executor in real production
            result = self.converter.convert(tmp_path)
            doc = result.document

            sections = []
            tables = []
            text_chunks = []

            # Extract text and sections
            for item, level in doc.iterate_items():
                if item.label == "text" or item.label == "paragraph":
                    text_chunks.append(item.text)
                elif item.label == "section_header":
                    sections.append(ParsedSection(
                        title=item.text,
                        level=level,
                        content="" # Will append content below in a more complex implementation
                    ))
                elif item.label == "table":
                    # Simple table extraction
                    table_data = []
                    if hasattr(item, 'data') and hasattr(item.data, 'grid'):
                        grid = item.data.grid
                        for row in grid:
                            table_data.append([cell.text for cell in row])
                    tables.append(ParsedTable(data=table_data))

            full_text = doc.export_to_markdown()

            return ParsedDocument(
                text=full_text,
                sections=sections,
                tables=tables,
                metadata={},
                parser_used="docling",
                raw_structured_payload={"docling_version": "native"} # Optional full dump
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def healthcheck(self) -> bool:
        return True

    def supports(self, mime_type: str, extension: str) -> bool:
        return extension.lower() in [".pdf", ".docx", ".pptx"] or mime_type in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]

    def capabilities(self) -> List[str]:
        return ["tables", "sections", "markdown", "ocr"]
