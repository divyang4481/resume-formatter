import io
import re
import logging
from typing import Any, Dict, List, Optional
from docxtpl import DocxTemplate, RichText
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

    def _apply_rendering_actions(self, content: Any) -> Any:
        """
        Hyper-Fidelity Composition Node: Recursively translatesproprietary
        CVML ([:B:], [:L1:], etc.) into native DOCX RichText runs.
        """
        # 1. Recursive handling for nested structures (Jobs, Projects, etc)
        if isinstance(content, dict):
            return {k: self._apply_rendering_actions(v) for k, v in content.items()}
        elif isinstance(content, list):
            return [self._apply_rendering_actions(v) for v in content]
        elif not isinstance(content, str):
            return content

        # 2. String Composition (The CVML Engine)
        if not any(tag in content for tag in ["[:B:]", "[:PIPE:]", "[:BR:]", "[:L1:]", "[:L2:]"]):
            return content

        rt = RichText()
        content = content.replace("\r\n", "\n")
        
        # Split into tokens: keep tags for processing
        parts = re.split(r'(\[:B:\].*?\[:/B:\]|\[:PIPE:\]|\[:BR:\]|\[:L1:\]|\[:L2:\])', content, flags=re.DOTALL)
        
        for part in parts:
            if not part:
                continue
                
            if part.startswith("[:B:]"):
                # [:B:]Bold Text[:/B:]
                inner = part[5:-6]
                rt.add(inner, bold=True)
            elif part == "[:PIPE:]":
                rt.add("  |  ")
            elif part == "[:BR:]":
                rt.add("\n")
            elif part == "[:L1:]":
                rt.add("\n• ")
            elif part == "[:L2:]":
                rt.add("\n    - ")
            else:
                # Standard text run
                rt.add(part)
                
        return rt
