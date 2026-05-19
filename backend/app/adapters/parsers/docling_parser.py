import io
import os
import tempfile
from typing import Any, Dict, List
from app.domain.interfaces.document_parser import DocumentParser
from app.schemas.parsed_document import ParsedDocument, ParsedSection, ParsedTable

class DoclingParser(DocumentParser):
    def __init__(self):
        self.converter = None

    async def parse(self, file_bytes: bytes, file_name: str, mime_type: str, options: Dict[str, Any] = None) -> ParsedDocument:
        if self.converter is None:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            pipeline_options.do_table_structure = True
            
            self.converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

        ext = os.path.splitext(file_name)[1]
        # On Windows, we must close the file before Docling can open it
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            tmp_path = tmp.name
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Docling parsing file: {file_name}, size: {len(file_bytes)} bytes")

        try:
            # Note: Docling processing is CPU bound, might want to run in an executor in real production
            result = self.converter.convert(tmp_path)
            doc = result.document
            
            full_text = doc.export_to_markdown()
            logger.info(f"Docling successfully converted {file_name}. Extracted text length: {len(full_text)}")

            sections = []
            tables = []
            text_chunks = []

            # Initial "Intro" section for any text appearing before the first header
            current_section = ParsedSection(title="Intro", level=1, content="")
            sections.append(current_section)

            # Extract text and sections
            for item, level in doc.iterate_items():
                # Recognize various header labels
                if item.label in ("section_header", "heading", "title"):
                    # If we found a real header, and our current section is just the empty Intro, rename it
                    if current_section and not current_section.content and current_section.title == "Intro":
                        current_section.title = item.text
                        current_section.level = level
                    else:
                        current_section = ParsedSection(
                            title=item.text,
                            level=level,
                            content=""
                        )
                        sections.append(current_section)
                # Recognize various text labels
                elif item.label in ("text", "paragraph", "list_item", "item", "caption", "footnote"):
                    txt = getattr(item, "text", "")
                    if txt:
                        text_chunks.append(txt)
                        if current_section:
                            if current_section.content:
                                current_section.content += "\n" + txt
                            else:
                                current_section.content = txt
                elif item.label == "table":
                    # Simple table extraction
                    table_data = []
                    if hasattr(item, 'data') and hasattr(item.data, 'grid'):
                        grid = item.data.grid
                        for row in grid:
                            table_data.append([getattr(cell, "text", "") for cell in row])
                    tables.append(ParsedTable(data=table_data))

            # Clean up: if Intro section is still empty at the end, remove it
            if sections and sections[0].title == "Intro" and not sections[0].content:
                sections.pop(0)

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
        return ["tables", "sections", "markdown"]
