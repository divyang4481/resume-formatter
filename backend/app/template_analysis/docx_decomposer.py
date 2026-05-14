import os
import logging
from app.services.template_structure_extractor import TemplateStructureExtractor
from .models import TemplateEvidence, PlaceholderCandidate, SectionCandidate, TableCandidate

logger = logging.getLogger(__name__)

def decompose_docx(file_path: Optional[str] = None, content: Optional[bytes] = None) -> TemplateEvidence:
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

    # Map markers
    for marker in structure.detected_markers:
        kind = "merge_marker"
        if "TableStart:" in marker:
            kind = "repeat_start"
        elif "TableEnd:" in marker:
            kind = "repeat_end"
        elif "[Type text]" in marker or "Type text" in marker:
            kind = "generic_fill_instruction"
        
        evidence.placeholder_candidates.append(PlaceholderCandidate(
            marker=marker,
            candidate_kind=kind,
            location="document_body",
            context_snippet=None # Could be improved by capturing surrounding text
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

    return evidence
