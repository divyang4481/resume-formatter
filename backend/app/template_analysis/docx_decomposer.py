import os
import logging
from typing import Optional
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

    # Load generic placeholders from config
    from app.services.template_structure_extractor import FIELD_ALIAS_MAP, TABLE_LOOP_PREFIX, TABLE_LOOP_SUFFIX
    generic_placeholders = FIELD_ALIAS_MAP.get("generic_placeholders", [])

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
            location="document_body",
            context_snippet=None 
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
