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

        # SMART REGEX: Captures most common marker types including << >>, {{ }}, [[ ]], [ ], and < >.
        # It also handles standard Jinja2/docxtpl variables.
        MARKER_PATTERN = r"<<\s*(.*?)\s*>>|\{\{\s*(.*?)\s*\}\}|\[\[\s*(.*?)\s*\]\]|\[\s*(.*?)\s*\]|<\s*(.*?)\s*>"

        def transform_paragraph_markers(text, fields, current_counter, manifest, ptr):
            new_text = text
            offset = 0
            
            # We want to iterate matches but avoid double-matching the replacements
            for match in list(re.finditer(MARKER_PATTERN, text)):
                start, end = match.span()
                original = match.group(0)
                
                # Extract inner content
                raw_marker_text = next((g for g in match.groups() if g is not None), "").strip()
                
                target_key = None
                
                # 1. SMART MANIFEST SEQUENTIAL MATCH
                if manifest and ptr[0] < len(manifest):
                    item_raw = manifest[ptr[0]]
                    item = item_raw.model_dump() if hasattr(item_raw, "model_dump") else (item_raw.dict() if hasattr(item_raw, "dict") else item_raw)
                    
                    is_generic = "fill" in raw_marker_text.lower() and "section" in raw_marker_text.lower()
                    if is_generic or original == item.get("tag") or raw_marker_text == item.get("tag"):
                        target_key = item.get("fieldname") or item.get("meaning")
                        if target_key:
                            ptr[0] += 1
                            replacement = f"{{{{ _['{target_key}'] }}}}"
                            new_text = new_text[:start + offset] + replacement + new_text[end + offset:]
                            offset += len(replacement) - (end - start)
                            continue

                # 2. LEGACY LOGIC FALLBACK
                if (
                    "fill" in raw_marker_text.lower()
                    and "section" in raw_marker_text.lower()
                ):
                    replacement = f"{{{{ _['section_{current_counter}'] }}}}"
                    new_text = new_text[: start + offset] + replacement + new_text[end + offset :]
                    offset += len(replacement) - len(original)
                    current_counter += 1
                elif raw_marker_text in fields:
                    replacement = f"{{{{ _['{raw_marker_text}'] }}}}"
                    new_text = new_text[: start + offset] + replacement + new_text[end + offset :]
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
        # 1. Recursive nested handling
        if isinstance(content, dict):
            return {k: self._apply_rendering_actions(v) for k, v in content.items()}
        elif isinstance(content, list):
            if not content: return ""
            return [self._apply_rendering_actions(v) for v in content]
        elif not isinstance(content, str):
            return content

        # 2. Composition Logic
        # Normalize bullets characters to Protocol tags
        content = re.sub(r'(?m)^[ \t]*[•\-\*][ \t]*', '[:L1:] ', content)

        # Splitting on ANY tag (opening or closing)
        tag_pattern = r'(?i)(\[:B:\]|\[:/B:\]|\[:PIPE:\]|\[:BR:\]|\[:L1:\]|\[:L2:\])'
        if not re.search(tag_pattern, content):
            return content

        rt = RichText()
        content = content.replace("\r\n", "\n")
        parts = re.split(tag_pattern, content)
        
        is_bold = False
        for part in parts:
            if not part: continue
            
            p_lower = part.lower()
            if p_lower == "[:b:]":
                is_bold = True
            elif p_lower == "[:/b:]":
                is_bold = False
            elif p_lower == "[:pipe:]":
                rt.add("  |  ", bold=is_bold)
            elif p_lower == "[:br:]":
                rt.add("\n")
            elif p_lower == "[:l1:]":
                rt.add("\n• ", bold=is_bold)
            elif p_lower == "[:l2:]":
                rt.add("\n    - ", bold=is_bold)
            else:
                rt.add(part, bold=is_bold)
                
        return rt


