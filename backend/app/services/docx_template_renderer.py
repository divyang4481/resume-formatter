import io
import re
import logging
import traceback
from typing import Any, Dict, List, Optional
from docxtpl import DocxTemplate, RichText
from docx import Document
from docx.text.paragraph import Paragraph

from app.schemas.template_analysis import TemplateAnalysis, TemplateFillPlan

logger = logging.getLogger(__name__)


class DocxTemplateRenderer:
    """
    Deterministic DOCX generator. Uses TemplateFillPlan to perform high-fidelity
    replacements without destroying original formatting.
    """

    def render(
        self,
        template_bytes: bytes,
        fill_plan: TemplateFillPlan,
        analysis: TemplateAnalysis,
    ) -> bytes:
        try:
            # 1. Phase 0: Physical Structural Manipulation (Instruction Clearing)
            doc = Document(io.BytesIO(template_bytes))
            self._clear_instructions(doc, fill_plan.instructions_to_clear)

            # 2. Phase 0.5: Direct AI-Marker Replacement
            # If the AI explicitly provided a marker text, we perform a direct replacement
            # as a high-priority fallback/override.
            self._direct_replace_ai_markers(doc, fill_plan.fields)

            # 3. Phase 1: Contextual Marker Injection
            # We transform the document into a Jinja2-ready docxtpl template
            self._inject_jinja_markers(doc, fill_plan, analysis)

            # 3. Phase 2: RichText Composition
            # Convert CVML tags ([:B:], etc) or simple lists into docxtpl RichText objects
            processed_context = self._prepare_render_context(fill_plan.fields)

            # 4. Phase 3: Final docxtpl Render
            buffer = io.BytesIO()
            doc.save(buffer)
            buffer.seek(0)

            tpl = DocxTemplate(buffer)

            # Case-insensitive context access
            class CaseInsensitiveDict(dict):
                def __getitem__(self, key):
                    if not isinstance(key, str):
                        return super().__getitem__(key)
                    val = super().get(key)
                    if val is not None:
                        return val
                    # Search case-insensitively
                    key_lower = key.lower()
                    for k, v in self.items():
                        if isinstance(k, str) and k.lower() == key_lower:
                            return v
                    return ""

            render_context = CaseInsensitiveDict(processed_context)
            render_context["_"] = (
                render_context  # Allow both {{ _['key'] }} and {{ key }}
            )

            tpl.render(render_context)

            output = io.BytesIO()
            tpl.save(output)
            return output.getvalue()

        except Exception as e:
            logger.exception("Document rendering failed with exception details:")
            raise RuntimeError(
                f"Failed to render document: {str(e)}\n{traceback.format_exc()}"
            )

    def _clear_instructions(self, doc, instructions: List[str]):
        """Physically removes instruction blocks from paragraphs and tables."""
        for text in instructions:
            if not text:
                continue
            # Normalize whitespace and case
            match_prefix = text.strip()[:100].replace("\xa0", " ").lower()

            # Paragraphs
            for p in doc.paragraphs:
                p_text_norm = p.text.replace("\xa0", " ").lower()
                if match_prefix in p_text_norm:
                    p.text = ""

            # Tables
            for tbl in doc.tables:
                for row in tbl.rows:
                    for cell in row.cells:
                        c_text_norm = cell.text.replace("\xa0", " ").lower()
                        if match_prefix in c_text_norm:
                            for p in cell.paragraphs:
                                p.text = ""

    def _direct_replace_ai_markers(self, doc, fields: Dict[str, Any]):
        """
        Uses markers explicitly identified by the AI to perform direct text replacement.
        This provides a highly reliable mapping that follows the AI's reasoning.
        """
        data_to_process = fields.get("template_fill_result", {})
        if not data_to_process:
            return

        logger.info("[Renderer] Performing Phase 0.5: Direct AI-Marker Replacement")
        for fieldname, info in data_to_process.items():
            if not isinstance(info, dict):
                continue

            marker = info.get("marker_text") or info.get("marker")
            value = info.get("value")

            if marker and value:
                # We only replace if the value is a string (scalars/rich text)
                # Complex objects like tables are still handled by Phase 1/2 Jinja injection
                if isinstance(value, str) and value != "N/A":
                    logger.info(
                        f"[Renderer] Direct replacing AI marker '{marker}' for field '{fieldname}'"
                    )
                    self._replace_text_in_doc(doc, marker, value)

    def _inject_jinja_markers(self, doc, fill_plan, analysis):
        """
        Replaces physical markers (guillemets, labels, headings) with Jinja2 tags
        based on the strategies defined in the analysis.
        """
        # Flatten all fields for easy lookup
        all_fields = list(analysis.fields)
        for s in analysis.sections:
            all_fields.extend(s.fields)

        for field in all_fields:
            strategy = field.render_locator.strategy
            fieldname = field.field_name

            logger.info(
                f"[Renderer] Processing field '{fieldname}' with strategy '{strategy}'"
            )

            if strategy in ("replace_marker", "replace_table_loop"):
                # Prioritize marker_text from manifest. For table loops, this creates a
                # safe fallback tag at the loop start; richer repeat rendering can use
                # the field's sub_fields from the manifest contract.
                marker = field.marker_text or field.render_locator.marker_text
                if not marker:
                    logger.warning(
                        f"[Renderer] No marker found for field '{fieldname}'"
                    )
                    continue
                logger.info(
                    f"[Renderer] Attempting to replace marker '{marker}' with field '{fieldname}'"
                )
                self._replace_text_in_doc(
                    doc, marker, f"{{{{ {fieldname} }}}}"
                )  # Using direct access for simplicity

            elif strategy == "fill_blank_cell_after_label":
                label = field.render_locator.label
                if not label:
                    continue
                # Also check if there's a marker in that cell we should replace instead of just blank
                marker = field.marker_text or field.render_locator.marker_text
                self._fill_cell_after_label(
                    doc, label, f"{{{{ {fieldname} }}}}", marker
                )

            elif strategy == "replace_section_body":
                heading = field.render_locator.heading
                if not heading:
                    continue
                self._replace_section_content(doc, heading, f"{{{{ {fieldname} }}}}")

    def _replace_text_in_doc(self, doc, target, replacement):
        """Helper to replace text in all document parts (Body, Headers, Footers, Tables)."""
        # 1. Main Body Paragraphs
        for p in doc.paragraphs:
            self._replace_in_paragraph(p, target, replacement)

        # 2. Main Body Tables (including nested)
        for tbl in doc.tables:
            self._replace_in_table(tbl, target, replacement)

        # 3. Headers and Footers
        for section in doc.sections:
            for header in [
                section.header,
                section.first_page_header,
                section.even_page_header,
            ]:
                if header:
                    for p in header.paragraphs:
                        self._replace_in_paragraph(p, target, replacement)
                    for tbl in header.tables:
                        self._replace_in_table(tbl, target, replacement)

            for footer in [
                section.footer,
                section.first_page_footer,
                section.even_page_footer,
            ]:
                if footer:
                    for p in footer.paragraphs:
                        self._replace_in_paragraph(p, target, replacement)
                    for tbl in footer.tables:
                        self._replace_in_table(tbl, target, replacement)

    def _replace_in_table(self, tbl, target, replacement):
        """Recursively scan table cells for markers."""
        for row in tbl.rows:
            for cell in row.cells:
                # Replace in cell paragraphs
                for p in cell.paragraphs:
                    self._replace_in_paragraph(p, target, replacement)
                # Handle nested tables
                for nested_tbl in cell.tables:
                    self._replace_in_table(nested_tbl, target, replacement)

    def _replace_in_paragraph(self, p, target, replacement):
        """Standard replacement within a paragraph with robustness for guillemet variants."""
        if not p.text:
            return

        # Normalize text to handle non-breaking spaces (\xA0) and other Word quirks
        text = p.text.replace("\xa0", " ").replace("\xa0", " ")
        norm_target = target.replace("\xa0", " ").replace("\xa0", " ")

        # 1. Direct match
        if norm_target in text:
            p.text = text.replace(norm_target, replacement)
            logger.info(f"[Renderer] Replaced marker '{norm_target}' in paragraph.")
            return

        # 2. Fuzzy match (normalized guillemets and brackets)
        clean_target = norm_target.strip("«»[]<> \t\n\r")
        variants = [
            f"«{clean_target}»",
            f"[{clean_target}]",
            f"<<{clean_target}>>",
            f"\xab{clean_target}\xbb",
            f"\u00ab{clean_target}\u00bb",
            clean_target,
        ]

        for variant in variants:
            if variant in text:
                p.text = text.replace(variant, replacement)
                logger.info(
                    f"[Renderer] Replaced fuzzy marker '{variant}' in paragraph."
                )
                return

        # 3. Regex fuzzy (handles internal whitespace like « CandidateName »)
        if len(clean_target) > 2:
            # Matches any start guillemet/bracket, optional whitespace, target, optional whitespace, any end guillemet/bracket
            pattern = re.compile(
                r"[\xab\u00ab\[<]+\s*"
                + re.escape(clean_target)
                + r"\s*[\xbb\u00bb\]>]+",
                re.I,
            )
            if pattern.search(text):
                p.text = pattern.sub(replacement, text)
                logger.info(
                    f"[Renderer] Replaced regex marker for '{clean_target}' in paragraph."
                )
                return

    def _fill_cell_after_label(self, doc, label, replacement, marker: str = None):
        """Finds a table cell with the label and fills the next cell."""
        for tbl in doc.tables:
            for row in tbl.rows:
                # Iterate through cells to find label
                cells = row.cells
                for i in range(len(cells)):
                    cell = cells[i]
                    if label.lower() in cell.text.lower():
                        if i + 1 < len(cells):
                            # Clear and replace next cell
                            target_cell = cells[i + 1]

                            # If we have a specific marker to target in that cell, use it
                            if marker and marker in target_cell.text:
                                for p in target_cell.paragraphs:
                                    self._replace_in_paragraph(p, marker, replacement)
                            else:
                                # Default: clear whole cell and inject tag
                                for p in target_cell.paragraphs:
                                    p.text = ""
                                if not target_cell.paragraphs:
                                    target_cell.add_paragraph(replacement)
                                else:
                                    target_cell.paragraphs[0].text = replacement
                            return

    def _replace_section_content(self, doc, heading, replacement):
        """Finds a heading, replaces the first following non-empty paragraph, and prunes all subsequent section paragraphs."""
        def is_heading_match(p_text: str, target_heading: str) -> bool:
            if not p_text or not target_heading:
                return False
            norm_p = re.sub(r'[^a-zA-Z0-9]', '', p_text).lower()
            norm_t = re.sub(r'[^a-zA-Z0-9]', '', target_heading).lower()
            return norm_p == norm_t

        def is_heading_boundary(p) -> bool:
            text = p.text.strip()
            if not text:
                return False
            style_name = p.style.name.lower() if p.style and p.style.name else ""
            if "heading" in style_name or style_name.startswith("h") and any(style_name.endswith(str(i)) for i in range(1, 7)):
                return True
            is_bold = any(run.bold for run in p.runs)
            if is_bold and len(text) < 60 and not text.startswith("["):
                return True
            if text.isupper() and len(text) < 60:
                return True
            return False

        for i, p in enumerate(doc.paragraphs):
            if is_heading_match(p.text, heading):
                # Find the first non-empty paragraph immediately following
                target_p = None
                for next_idx in range(i + 1, len(doc.paragraphs)):
                    next_p = doc.paragraphs[next_idx]
                    if next_p.text.strip():
                        target_p = next_p
                        break
                
                if target_p:
                    target_p.text = replacement
                    logger.info(f"[Renderer] Replaced first section body paragraph under heading '{p.text}'")
                    
                    # Scan and physically remove subsequent placeholder paragraphs in that section
                    curr = target_p._element.getnext()
                    to_delete = []
                    while curr is not None:
                        tag = curr.tag
                        if tag.endswith("tbl"):
                            break
                        elif tag.endswith("p"):
                            p_obj = Paragraph(curr, doc)
                            if is_heading_boundary(p_obj):
                                break
                            to_delete.append(curr)
                        curr = curr.getnext()
                    
                    if to_delete:
                        logger.info(f"[Renderer] Pruned {len(to_delete)} placeholder paragraphs from section '{p.text}'")
                        for elm in to_delete:
                            elm.getparent().remove(elm)
                    return

    def _replace_complex_block(self, doc, start_marker, replacement, context_heading=None):
        """Replaces a multiline complex block bounded by specific markers."""
        # Simple naive implementation: try to find start marker, replace its text,
        # and prune the rest of the block if possible, or just inject directly.
        for p in doc.paragraphs:
            if start_marker and start_marker in p.text:
                self._replace_in_paragraph(p, start_marker, replacement)
                logger.info(f"[Renderer] Replaced complex block starting with '{start_marker}'")
                return
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        if start_marker and start_marker in p.text:
                            self._replace_in_paragraph(p, start_marker, replacement)
                            logger.info(f"[Renderer] Replaced complex block in table starting with '{start_marker}'")
                            return


    def _format_complex_list(self, v: list) -> str:
        formatted_lines = []
        for item in v:
            if "job_title" in item or "company" in item:
                title = item.get("job_title", "Position")
                company = item.get("company", "Company")
                dates = f"{item.get('start_date', '')} - {item.get('end_date', 'Present')}"
                desc = (
                    item.get("description")
                    or item.get("responsibilities")
                    or ""
                )
                block = f"• {title} | {company} ({dates})"
                if desc:
                    if isinstance(desc, list):
                        desc_str = "\n  - " + "\n  - ".join(desc)
                        block += desc_str
                    else:
                        block += f"\n  {desc}"
                formatted_lines.append(block)
            elif "degree" in item or "institution" in item:
                degree = item.get("degree", "Qualification")
                school = item.get("institution", "Institution")
                year = item.get("graduation_year") or item.get("year") or ""
                formatted_lines.append(f"• {degree}, {school} ({year})")
            else:
                formatted_lines.append(f"• {str(item)}")
        return "\n\n".join(formatted_lines)

    def _prepare_render_context(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Converts raw data into docxtpl-friendly RichText or formatted strings."""
        context = {}

        # Check if fields is the "Deep Reasoning" structure (has template_fill_result)
        # If so, we extract the actual values from the result mapping.
        if "template_fill_result" in fields:
            raw_fields = fields["template_fill_result"]
            processed_fields = {}
            for k, v in raw_fields.items():
                if isinstance(v, dict) and "value" in v:
                    processed_fields[k] = v["value"]
                else:
                    processed_fields[k] = v
        else:
            processed_fields = fields

        for k, v in processed_fields.items():
            if isinstance(v, list):
                if not v:
                    context[k] = "N/A"
                    continue

                # Check if this is a list of complex objects (Work Exp, Education)
                if isinstance(v[0], dict):
                    formatted_lines = []
                    for item in v:
                        # Professional formatting for Job Experience
                        if "job_title" in item or "company" in item:
                            title = item.get("job_title", "Position")
                            company = item.get("company", "Company")
                            dates = f"{item.get('start_date', '')} - {item.get('end_date', 'Present')}"
                            desc = (
                                item.get("description")
                                or item.get("responsibilities")
                                or ""
                            )

                            block = f"• {title} | {company} ({dates})"
                            if desc:
                                if isinstance(desc, list):
                                    desc_str = "\n  - " + "\n  - ".join(desc)
                                    block += desc_str
                                else:
                                    block += f"\n  {desc}"
                            formatted_lines.append(block)

                        # Professional formatting for Education
                        elif "degree" in item or "institution" in item:
                            degree = item.get("degree", "Qualification")
                            school = item.get("institution", "Institution")
                            year = item.get("graduation_year") or item.get("year") or ""
                            formatted_lines.append(f"• {degree}, {school} ({year})")

                        else:
                            # Fallback for unknown objects
                            formatted_lines.append(f"• {str(item)}")

                    context[k] = "\n\n".join(formatted_lines)
                else:
                    # Simple list of strings -> Bulleted list
                    context[k] = "\n".join([f"• {str(item)}" for item in v])
            else:
                context[k] = v or "N/A"
        return context
