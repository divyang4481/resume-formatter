import os
import logging
from typing import Optional
from app.services.template_structure_extractor import TemplateStructureExtractor
from .models import TemplateEvidence, PlaceholderCandidate, SectionCandidate, TableCandidate

logger = logging.getLogger(__name__)

def _extract_with_docling_sync(content: bytes, filename: str) -> Optional[str]:
    """Helper to synchronously extract structural markdown using Docling."""
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        import tempfile

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        ext = os.path.splitext(filename)[1] or ".docx"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            tmp_path = tmp.name

        try:
            result = converter.convert(tmp_path)
            markdown_text = result.document.export_to_markdown()
            logger.info(f"Docling successfully extracted template markdown ({len(markdown_text)} chars)")
            return markdown_text
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        logger.warning(f"Docling template extraction failed or docling not installed: {e}")
        return None

def decompose_docx(file_path: Optional[str] = None, content: Optional[bytes] = None, docling_text: Optional[str] = None) -> TemplateEvidence:
    """
    Reads a DOCX file and decomposes it into structural evidence.
    Wraps TemplateStructureExtractor and maps it to the new TemplateEvidence model.
    """
    if content is None:
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Template file not found or content missing: {file_path}")

        with open(file_path, "rb") as f:
            content = f.read()

    filename = os.path.basename(file_path) if file_path else "template.docx"
    extractor = TemplateStructureExtractor()
    structure = extractor.extract(content, filename)

    evidence = TemplateEvidence()

    # Load generic placeholders from config
    from app.services.template_structure_extractor import FIELD_ALIAS_MAP, TABLE_LOOP_PREFIX, TABLE_LOOP_SUFFIX
    generic_placeholders = FIELD_ALIAS_MAP.get("generic_placeholders", [])

    # Preserve full deterministic ground truth for prompts, validators, and debugging.
    evidence.raw_structure = structure.to_dict()
    evidence.layout_style = structure.layout_style
    evidence.paste_zones = list(structure.paste_zones)
    evidence.header_footer_markers = list(structure.headers_footers_markers)
    evidence.table_loops = [loop.to_dict() for loop in structure.table_loops]
    evidence.table_loop_fields = {loop.loop_name: list(loop.item_fields) for loop in structure.table_loops}
    evidence.heading_to_loop = dict(structure.heading_to_loop)
    evidence.blank_label_slots = list(structure.blank_label_slots)

    # ── Handle Docling Layout Extraction ──
    if docling_text:
        evidence.docling_markdown = docling_text
    else:
        evidence.docling_markdown = _extract_with_docling_sync(content, filename)

    evidence.raw_text_summary = evidence.docling_markdown or "\n".join(structure.doc_lines)

    heading_context_by_marker = {}
    for heading, markers in structure.heading_to_smart_pattern.items():
        for marker in markers:
            heading_context_by_marker[marker] = f"Under heading: {heading}"

    table_context_by_marker = {
        slot.marker_text: f"Table label: {slot.label}; blank value cell: {slot.is_blank}"
        for slot in structure.table_label_value_pairs
        if slot.marker_text
    }

    # Map markers
    for marker in structure.detected_markers:
        kind = "merge_marker"
        if marker.strip("«»").startswith(TABLE_LOOP_PREFIX.strip(":")):
            kind = "repeat_start"
        elif marker.strip("«»").startswith(TABLE_LOOP_SUFFIX.strip(":")):
            kind = "repeat_end"
        elif any(gp.lower() in marker.lower() for gp in generic_placeholders):
            kind = "context_placeholder"
        
        evidence.placeholder_candidates.append(PlaceholderCandidate(
            marker=marker,
            candidate_kind=kind,
            location="header_footer" if marker in structure.headers_footers_markers else "document_body",
            context_snippet=table_context_by_marker.get(marker) or heading_context_by_marker.get(marker)
        ))

    # Map sections/headings
    for heading in structure.all_headings:
        evidence.section_candidates.append(SectionCandidate(
            heading=heading,
            level=1, # Heuristic
            content_snippet=structure.heading_to_placeholder.get(heading)
        ))

    # Map tables
    for i, slot in enumerate(structure.table_label_value_pairs):
        evidence.tables.append(TableCandidate(
            label=slot.label,
            marker=slot.marker_text,
            is_blank=slot.is_blank,
            row_index=i
        ))

    # Map instructions
    evidence.instruction_blocks = structure.instruction_blocks

    # Map object patterns (headings -> multi-line placeholders)
    evidence.object_patterns = structure.heading_to_smart_pattern

    # Map repeated markers
    evidence.repeated_markers = structure.repeated_markers

    # Map bullet slots
    evidence.bullet_slots = structure.bullet_slots

    return evidence
