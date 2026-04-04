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
        field_extraction_manifest: Optional[List[Dict[str, str]]] = None,
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

            # Provide the manifest list directly to the marker preparer
            manifest_list = []
            if field_extraction_manifest:
                if isinstance(field_extraction_manifest, str):
                    try:
                        manifest_list = json.loads(field_extraction_manifest)
                    except:
                        manifest_list = []
                elif isinstance(field_extraction_manifest, list):
                    manifest_list = field_extraction_manifest

            processed_template_stream = self.prepare_document_markers(
                template_stream, expected_fields_list, manifest_list
            )

            # 2. Apply "Rendering Actions" to transform structured data into professional document prose
            processed_resume_data = self._apply_rendering_actions(resume_data)

            # 3. Render final content using docxtpl
            doc = DocxTemplate(processed_template_stream)

            # Universal Scoped Context mapping: Create a flat, semantic lookup for markers.
            # The manifest ensures that document tags resolve to these keys.
            render_context = {**processed_resume_data}
            render_context_with_scope = {
                **render_context, 
                "_": self._flatten_dict(render_context)
            }

            doc.render(render_context_with_scope)

            # 4. Save to bytes (preserving original formatting)
            out_stream = io.BytesIO()
            doc.save(out_stream)
            return out_stream.getvalue()

        except Exception as e:
            logger.error(f"Document rendering failed: {e}")
            raise RuntimeError(f"Failed to render document: {str(e)}")

    def prepare_document_markers(
        self, template_stream: io.BytesIO, field_list: List[str], manifest_list: Optional[List[Dict[str, Any]]] = None
    ) -> io.BytesIO:
        """
        Scans the document for various marker patterns (<< >>, {{ }}, [[ ]]) and 
        normalizes them to use the scoped 'Universal Context' dictionary lookup.
        """
        doc = Document(template_stream)
        counter = 0
        manifest_list = manifest_list or []
        # Use simple list for pass-by-reference counter
        manifest_ptr = [0] 

        # Regex for common placeholder patterns: << >>, {{ }}, [[ ]]
        MARKER_PATTERN = r"(?:<<|\{\{|\[\[)\s*(.*?)\s*(?:>>|\}\}|\]\])"

        def transform_paragraph_markers(text, fields, current_counter, manifest, ptr):
            matches = re.finditer(MARKER_PATTERN, text)
            new_text = text
            offset = 0
            for match in matches:
                original = match.group(0)
                raw_marker_text = match.group(1).strip()

                # SEMANTIC SEQUENTIAL RECOVERY:
                # If we have a manifest and we're not past the end...
                if manifest and ptr[0] < len(manifest):
                    item = manifest[ptr[0]]
                    # Match by raw tag or inner text
                    if original == item.get("tag") or raw_marker_text == item.get("tag") or raw_marker_text == item.get("inner_label"):
                        target_key = item.get("meaning")
                        replacement = f"{{{{ _['{target_key}'] }}}}"
                        ptr[0] += 1
                        start, end = match.span()
                        new_text = (
                            new_text[: start + offset] + replacement + new_text[end + offset :]
                        )
                        offset += len(replacement) - len(original)
                        continue

                # FALLBACK LOGIC
                if (
                    "fill" in raw_marker_text.lower()
                    and "section" in raw_marker_text.lower()
                    and current_counter < len(fields)
                ):
                    target_key = fields[current_counter]
                    replacement = f"{{{{ _['{target_key}'] }}}}"
                    current_counter += 1
                else:
                    # Map visual marker to its logical value
                    safe_key = raw_marker_text.lower().replace(" ", "_")
                    replacement = f"{{{{ _['{safe_key}'] }}}}"

                start, end = match.span()
                new_text = (
                    new_text[: start + offset] + replacement + new_text[end + offset :]
                )
                offset += len(replacement) - len(original)
            return new_text, current_counter

        # Process all structural elements in the document
        for p in doc.paragraphs:
            if "<<" in p.text or "{{" in p.text or "[[" in p.text:
                p.text, counter = transform_paragraph_markers(p.text, field_list, counter, manifest_list, manifest_ptr)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        if "<<" in p.text or "{{" in p.text or "[[" in p.text:
                            p.text, counter = transform_paragraph_markers(p.text, field_list, counter, manifest_list, manifest_ptr)

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

    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
        """
        Recursively flattens a nested dictionary into dot-notation keys.
        Example: {'a': {'b': 1}} -> {'a.b': 1}
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

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
