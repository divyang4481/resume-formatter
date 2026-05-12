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
        field_manifest: Optional[List[Dict[str, Any]]] = None
    ) -> tuple[bytes, List[str]]:
        """
        Takes raw template bytes and AI-harmonized data, prepares the document markers,
        and renders the final DOCX file.
        """
        try:
            template_stream = io.BytesIO(template_bytes)

            expected_fields_list = [
                f.strip() for f in expected_fields.split(",") if f.strip()
            ]

            processed_template_stream = self.prepare_document_markers(
                template_stream, expected_fields_list, field_manifest
            )

            # 2. Apply "Rendering Actions" to transform structured data into professional document prose
            processed_resume_data = self._apply_rendering_actions(resume_data)

            # 3. Render final content using docxtpl
            doc = DocxTemplate(processed_template_stream)

            # Flatten the context for universal access
            def flatten_dict(d, parent_key='', sep='_'):
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    else:
                        items.append((k, v)) # Add the leaf key
                        if parent_key:
                            items.append((new_key, v)) # Also add the path-based key
                return dict(items)

            flattened_context = flatten_dict(processed_resume_data)
            
            # Prepare render context
            render_context = {**processed_resume_data, **flattened_context}
            
            # Universal Scoped Context mapping logic:
            # We create a mapping that supports:
            # 1. Original keys
            # 2. Lowercase snake_case (employee_email)
            # 3. Clean alphanumeric (employeeemail)
            normalized_context = {}
            for k, v in render_context.items():
                normalized_context[k] = v
                
                # Standardize key for lookup
                def standardize(key):
                    return "".join(filter(str.isalnum, key.lower()))
                
                norm_k = standardize(k)
                normalized_context[norm_k] = v

            # Create a "Smart Context" that handles missing keys by trying standardized versions
            class CaseInsensitiveDict(dict):
                def __getitem__(self, key):
                    if key in self:
                        val = super().__getitem__(key)
                        return val if val is not None else ""
                    
                    # Try standardized version
                    std_key = "".join(filter(str.isalnum, key.lower()))
                    if std_key in self:
                        val = super().__getitem__(std_key)
                        return val if val is not None else ""
                    
                    # Fallback to snake_case if key is PascalCase
                    snake_key = re.sub(r'(?<!^)(?=\[A-Z\])', '_', key).lower()
                    if snake_key in self:
                        val = super().__getitem__(snake_key)
                        return val if val is not None else ""
                        
                    return "" # Return empty string instead of None to prevent 'None' appearing in Docx

            smart_context = CaseInsensitiveDict(normalized_context)
            render_context_with_scope = {**render_context, **smart_context, "_": smart_context}
            
            # --- MISSING FIELD VALIDATION ---
            missing_fields = []
            all_target_keys = set()
            if field_manifest:
                all_target_keys.update([item["fieldname"] for item in field_manifest])
            if expected_fields_list:
                all_target_keys.update(expected_fields_list)
            
            for key in all_target_keys:
                val = render_context_with_scope.get("_", {}).get(key)
                if val is None or val == "" or (isinstance(val, str) and "not found" in val.lower()):
                    missing_fields.append(key)
            
            if missing_fields:
                logger.warning(f"RENDERING WARNING: The following template fields remained empty: {missing_fields}")

            doc.render(render_context_with_scope)

            # 4. Save to bytes
            out_stream = io.BytesIO()
            doc.save(out_stream)
            return out_stream.getvalue(), missing_fields

        except Exception as e:
            logger.error(f"Document rendering failed: {e}")
            raise RuntimeError(f"Failed to render document: {str(e)}")

    def prepare_document_markers(
        self, 
        template_stream: io.BytesIO, 
        field_list: List[str],
        field_manifest: Optional[List[Dict[str, Any]]] = None
    ) -> io.BytesIO:
        """
        Scans the document for various marker patterns and normalizes them.
        Uses manifest 'marker_text' as primary anchors for high-precision replacement.
        """
        doc = Document(template_stream)
        counter = 0

        # Regex for common placeholder patterns
        MARKER_PATTERN = r"(?:<<|\{\{|\[\[|«|\[)\s*(.*?)\s*(?:>>|\}\}|\]\]|»|\])"

        def transform_text(text, fields, current_counter, manifest):
            matches = list(re.finditer(MARKER_PATTERN, text))
            new_text = text
            offset = 0
            
            for match in matches:
                original = match.group(0)
                raw_marker_text = match.group(1).strip()
                target_key = None
                
                # 1. Try to find in manifest by literal marker_text match
                if manifest:
                    for item in manifest:
                        m_text = item.get("marker_text", "")
                        # Try exact match, or match without the brackets if LLM missed them in the manifest
                        if m_text == original or m_text == raw_marker_text or f"«{m_text}»" == original:
                            target_key = item.get("fieldname")
                            logger.info(f"Manifest Match: Found '{original}', mapping to '{target_key}'")
                            break
                
                # 2. Sequential mapping for generic markers
                if not target_key:
                    generic_keywords = ["type text", "fill", "placeholder", "organisation", "organization", "job description", "institution", "degree", "bullet point"]
                    is_generic = any(x in raw_marker_text.lower() for x in generic_keywords)
                    if is_generic and current_counter < len(fields):
                        target_key = fields[current_counter]
                        current_counter += 1
                        logger.info(f"Generic Match: Mapping '{original}' to '{target_key}' (sequential)")

                # 3. Smart Fuzzy Mapping for common resume fields
                if not target_key:
                    # Normalize raw_marker_text
                    clean_marker = re.sub(r'[^a-z0-9]', '', raw_marker_text.lower())
                    for field in fields:
                        clean_field = re.sub(r'[^a-z0-9]', '', field.lower())
                        if clean_marker == clean_field or clean_marker in clean_field or clean_field in clean_marker:
                            if "name" in clean_marker and "name" in clean_field:
                                target_key = field
                                logger.info(f"Smart Match (Name): Mapping '{original}' to '{target_key}'")
                                break
                            if "email" in clean_marker and "email" in clean_field:
                                target_key = field
                                logger.info(f"Smart Match (Email): Mapping '{original}' to '{target_key}'")
                                break
                            if "summary" in clean_marker and "summary" in clean_field:
                                target_key = field
                                logger.info(f"Smart Match (Summary): Mapping '{original}' to '{target_key}'")
                                break
                
                # 4. Fallback to raw marker text
                if not target_key:
                    target_key = raw_marker_text
                    logger.info(f"Fallback Match: Using raw marker text '{target_key}' for '{original}'")
                
                replacement = f"{{{{ _['{target_key}'] }}}}"
                start, end = match.span()
                new_text = (
                    new_text[: start + offset] + replacement + new_text[end + offset :]
                )
                offset += len(replacement) - len(original)
            
            return new_text, current_counter

        def process_paragraph(paragraph, fields, current_counter, manifest):
            full_text = paragraph.text
            
            # Check for instructional anchors from manifest first
            if manifest:
                for item in manifest:
                    anchor = item.get("marker_text")
                    if anchor and anchor in full_text and not any(m in anchor for m in ["<<", "«", "{{", "[[", "["]):
                        # This is a non-marker instructional anchor (like "Paste CV here")
                        paragraph.text = f"{{{{ _['{item.get('fieldname')}'] }}}}"
                        logger.info(f"Anchor matched and replaced: {anchor}")
                        return current_counter

            # Then check for formal markers
            has_marker = any(m in full_text for m in ["<<", "{{", "[[", "«", "["])
            if has_marker:
                new_text, next_counter = transform_text(full_text, fields, current_counter, manifest)
                if new_text != full_text:
                    if len(paragraph.runs) == 1:
                        paragraph.runs[0].text = new_text
                    else:
                        # Fallback: preserve the formatting of the first run if it exists
                        first_run_style = None
                        if paragraph.runs:
                            try:
                                first_run_style = paragraph.runs[0].style
                            except:
                                pass
                        
                        paragraph.text = ""
                        run = paragraph.add_run(new_text)
                        # Only apply if it's a CHARACTER style (type 2) to avoid docx error
                        if first_run_style and hasattr(first_run_style, 'type') and first_run_style.type == 2:
                            run.style = first_run_style
                return next_counter
            
            return current_counter

        # Process all structural elements
        for section in doc.sections:
            for header in [section.header, section.first_page_header, section.even_page_header]:
                if header:
                    for p in header.paragraphs:
                        counter = process_paragraph(p, field_list, counter, field_manifest)
                    for table in header.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                for p in cell.paragraphs:
                                    counter = process_paragraph(p, field_list, counter, field_manifest)
            
            for footer in [section.footer, section.first_page_footer, section.even_page_footer]:
                if footer:
                    for p in footer.paragraphs:
                        counter = process_paragraph(p, field_list, counter, field_manifest)
                    for table in footer.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                for p in cell.paragraphs:
                                    counter = process_paragraph(p, field_list, counter, field_manifest)

        for p in doc.paragraphs:
            counter = process_paragraph(p, field_list, counter, field_manifest)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        counter = process_paragraph(p, field_list, counter, field_manifest)

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
