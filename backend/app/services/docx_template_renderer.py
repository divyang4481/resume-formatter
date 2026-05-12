import io
import re
import logging
from typing import Any, Dict, List, Optional
from docxtpl import DocxTemplate, RichText
from docx import Document

from app.schemas.template_analysis import TemplateAnalysis, TemplateFillPlan

logger = logging.getLogger(__name__)

class DocxTemplateRenderer:
    """
    Deterministic DOCX generator. Uses TemplateFillPlan to perform high-fidelity 
    replacements without destroying original formatting.
    """

    def render(self, template_bytes: bytes, fill_plan: TemplateFillPlan, analysis: TemplateAnalysis) -> bytes:
        try:
            # 1. Phase 0: Physical Structural Manipulation (Instruction Clearing)
            doc = Document(io.BytesIO(template_bytes))
            self._clear_instructions(doc, fill_plan.instructions_to_clear)
            
            # 2. Phase 1: Contextual Marker Injection
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
            # Add CaseInsensitive helper for context access
            render_context = {**processed_context, "_": processed_context}
            
            tpl.render(render_context)
            
            output = io.BytesIO()
            tpl.save(output)
            return output.getvalue()

        except Exception as e:
            logger.error(f"[Renderer] Failed to render document: {e}")
            raise

    def _clear_instructions(self, doc, instructions: List[str]):
        """Physically removes instruction blocks from paragraphs and tables."""
        for text in instructions:
            if not text: continue
            match_prefix = text.strip()[:100]
            
            # Paragraphs
            for p in doc.paragraphs:
                if match_prefix in p.text:
                    p.text = ""
            
            # Tables
            for tbl in doc.tables:
                for row in tbl.rows:
                    for cell in row.cells:
                        if match_prefix in cell.text:
                            for p in cell.paragraphs:
                                p.text = ""

    def _inject_jinja_markers(self, doc, fill_plan, analysis):
        """
        Replaces physical markers (guillemets, labels, headings) with Jinja2 tags
        based on the strategies defined in the analysis.
        """
        # Flatten all fields for easy lookup
        all_fields = list(analysis.fields)
        for s in analysis.sections: all_fields.extend(s.fields)

        for field in all_fields:
            strategy = field.render_locator.strategy
            fieldname = field.field_name
            
            if strategy == "replace_marker":
                marker = field.marker_text or field.render_locator.marker
                if not marker: continue
                self._replace_text_in_doc(doc, marker, f"{{{{ _['{fieldname}'] }}}}")
            
            elif strategy == "fill_blank_cell_after_label":
                label = field.render_locator.label
                if not label: continue
                self._fill_cell_after_label(doc, label, f"{{{{ _['{fieldname}'] }}}}")
                
            elif strategy == "replace_section_body":
                heading = field.render_locator.heading
                if not heading: continue
                self._replace_section_content(doc, heading, f"{{{{ _['{fieldname}'] }}}}")

    def _replace_text_in_doc(self, doc, target, replacement):
        """Helper to replace text in all document parts."""
        # Main paragraphs
        for p in doc.paragraphs:
            if target in p.text:
                p.text = p.text.replace(target, replacement)
        # Tables
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    if target in cell.text:
                        for p in cell.paragraphs:
                            p.text = p.text.replace(target, replacement)

    def _fill_cell_after_label(self, doc, label, replacement):
        """Finds a table cell with the label and fills the next cell."""
        for tbl in doc.tables:
            for row in tbl.rows:
                for i, cell in enumerate(row.cells):
                    if label.lower() in cell.text.lower():
                        if i + 1 < len(row.cells):
                            # Clear and replace next cell
                            target_cell = row.cells[i+1]
                            for p in target_cell.paragraphs: p.text = ""
                            target_cell.paragraphs[0].text = replacement
                            return

    def _replace_section_content(self, doc, heading, replacement):
        """Finds a heading and replaces the paragraph immediately following it."""
        for i, p in enumerate(doc.paragraphs):
            if heading.lower() in p.text.lower():
                if i + 1 < len(doc.paragraphs):
                    doc.paragraphs[i+1].text = replacement
                    return

    def _prepare_render_context(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Converts raw data into docxtpl-friendly RichText if needed."""
        context = {}
        for k, v in fields.items():
            if isinstance(v, list):
                # Simple list -> Bulleted RichText
                rt = RichText()
                for i, item in enumerate(v):
                    rt.add(f"• {item}")
                    if i < len(v) - 1: rt.add("\n")
                context[k] = rt
            else:
                context[k] = v or ""
        return context
