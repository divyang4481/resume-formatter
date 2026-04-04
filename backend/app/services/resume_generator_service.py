import io
import re
import logging
from typing import Any, Dict, List, Optional
from docxtpl import DocxTemplate
from docx import Document

logger = logging.getLogger(__name__)


class ResumeGeneratorService:
    """
    Handles the physical generation of resume documents (DOCX rendering).
    Extracts the template manipulation logic out of the agent nodes into a reusable service.
    """

    def render_formatted_document(
        self,
        template_bytes: bytes,
        resume_data: Dict[str, Any],
        expected_fields: Optional[str] = "",
    ) -> bytes:
        """
        Takes raw template bytes and AI-harmonized data, prepares the document markers,
        and renders the final DOCX file.
        """
        try:
            template_stream = io.BytesIO(template_bytes)

            # 1. Normalize markers across styles: Convert <<...>>, {{...}}, and [[...]] 
            # into a unified logical mapping for the rendering engine.
            expected_fields_list = [
                f.strip() for f in expected_fields.split(",") if f.strip()
            ]

            processed_template_stream = self.prepare_document_markers(
                template_stream, expected_fields_list
            )

            # 2. Apply "Rendering Actions" to transform structured data into professional document prose
            processed_resume_data = self._apply_rendering_actions(resume_data)

            # 3. Render final content using docxtpl
            doc = DocxTemplate(processed_template_stream)

            # Prepare render context (merge nested personal_info for easier access)
            render_context = {**processed_resume_data}
            if "personal_info" in processed_resume_data and isinstance(
                processed_resume_data["personal_info"], dict
            ):
                render_context.update(processed_resume_data["personal_info"])

            # Universal Scoped Context mapping logic:
            render_context_with_scope = {**render_context, "_": {**render_context}}

            logger.info(
                f"RENDERING DOCUMENT: {len(render_context_with_scope['_'])} labels available in context."
            )
            
            doc.render(render_context_with_scope)

            # 4. Save to bytes (preserving original formatting)
            out_stream = io.BytesIO()
            doc.save(out_stream)
            return out_stream.getvalue()

        except Exception as e:
            logger.error(
                f"Document rendering failed: {e}. Available keys in data: {list(render_context.keys()) if 'render_context' in locals() else 'Unknown'}"
            )
            raise RuntimeError(f"Failed to render document: {str(e)}")

    def prepare_document_markers(
        self, template_stream: io.BytesIO, field_list: List[str]
    ) -> io.BytesIO:
        """
        Scans the document for various marker patterns (<< >>, {{ }}, [[ ]]) and 
        normalizes them to use the scoped 'Universal Context' dictionary lookup.
        """
        doc = Document(template_stream)
        counter = 0

        # Regex for common placeholder patterns: << >>, {{ }}, [[ ]]
        MARKER_PATTERN = r"(?:<<|\{\{|\[\[)\s*(.*?)\s*(?:>>|\}\}|\]\])"

        def transform_paragraph_markers(text, fields, current_counter):
            matches = re.finditer(MARKER_PATTERN, text)
            new_text = text
            offset = 0
            for match in matches:
                original = match.group(0)
                raw_marker_text = match.group(1).strip()

                # 1. Identify 'fill' placeholders (sequential mapping)
                is_fill_section = (
                    "fill" in raw_marker_text.lower()
                    and "section" in raw_marker_text.lower()
                )

                if is_fill_section and current_counter < len(fields):
                    # Map generic marker to specific AI field
                    target_key = fields[current_counter]
                    replacement = f"{{{{ _['{target_key}'] }}}}"
                    current_counter += 1
                elif is_fill_section:
                    replacement = f"{{{{ _['missing_field_{current_counter}'] }}}}"
                    current_counter += 1
                else:
                    # 2. Map visual marker to its logical value in context
                    # Any marker text now becomes a valid dictionary key.
                    replacement = f"{{{{ _['{raw_marker_text}'] }}}}"

                start, end = match.span()
                new_text = (
                    new_text[: start + offset] + replacement + new_text[end + offset :]
                )
                offset += len(replacement) - len(original)
            return new_text, current_counter

        # Process all structural elements in the document
        for p in doc.paragraphs:
            if "<<" in p.text or "{{" in p.text or "[[" in p.text:
                p.text, counter = transform_paragraph_markers(p.text, field_list, counter)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        if "<<" in p.text or "{{" in p.text or "[[" in p.text:
                            p.text, counter = transform_paragraph_markers(p.text, field_list, counter)

        processed_stream = io.BytesIO()
        doc.save(processed_stream)
        processed_stream.seek(0)
        return processed_stream

    def generate_error_docx(self, template_id: str, error_message: str) -> bytes:
        """
        Generates a valid (but minimal) DOCX file containing failure details,
        ensuring the user doesn't get a corrupted file error from Word.
        """
        from docx import Document
        error_doc = Document()
        error_doc.add_heading("TEMPLATE RENDERING ERROR", level=1)
        error_doc.add_paragraph(f"Template Identification: {template_id}")
        error_doc.add_paragraph("-" * 20)
        error_doc.add_paragraph(f"Failure reason detected by system:")
        error_doc.add_paragraph(error_message)

        error_stream = io.BytesIO()
        error_doc.save(error_stream)
        return error_stream.getvalue()

    def _apply_rendering_actions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Visual Block Composer: Translates proprietary CVML ([:L1:], [:B:], etc.) 
        into native document formatting, including RICH TEXT for bolding. 
        """
        from docxtpl import RichText
        
        processed_data = {}
        for key, value in data.items():
            if not isinstance(value, str):
                processed_data[key] = str(value)
                continue
                
            # If the text has CVML bolding, we must convert it to a RichText object
            if "[:B:]" in value:
                rt = RichText()
                # Split by bold tags to build the RichText runs
                parts = re.split(r"(\[:B:\].*?\[:/B:\]|\[:L1:\]|\[:L2:\]|\[:PIPE:\]|\[:BR:\])", value)
                
                for part in parts:
                    if not part: continue
                    
                    if part.startswith("[:B:]") and part.endswith("[:/B:]"):
                        rt.add(part[5:-6], bold=True)
                    elif part == "[:L1:]":
                        rt.add("• ")
                    elif part == "[:L2:]":
                        rt.add("    - ")
                    elif part == "[:PIPE:]":
                        rt.add(" | ")
                    elif part == "[:BR:]":
                        rt.add("\n")
                    else:
                        rt.add(part)
                processed_data[key] = rt
            else:
                # Handle non-bold but still containing structural CVML
                processed_data[key] = self._render_visual_markup(value)
            
        return processed_data

    def _render_visual_markup(self, text: str) -> str:
        """
        Translates CVML reserved keywords into professional document prose.
        Standard text version (fallback).
        """
        if not text:
            return ""
            
        processed = text
        processed = processed.replace("[:L1:]", "• ")
        processed = processed.replace("[:L2:]", "    - ")
        processed = processed.replace("[:PIPE:]", " | ")
        processed = processed.replace("[:BR:]", "\n")
        processed = processed.replace("[:B:]", "").replace("[:/B:]", "")
        
        return processed.strip()
