from typing import List, Tuple
from .models import TemplateEvidence, TemplateManifest


def validate_manifest_against_evidence(
    manifest: TemplateManifest,
    evidence: TemplateEvidence
) -> Tuple[List[str], List[str]]:
    """
    Performs deterministic validation of the manifest against the structural evidence.
    Returns (errors, warnings).
    """
    errors = []
    warnings = []

    # 1. Check for missing placeholders
    evidence_markers = {ph.marker for ph in evidence.placeholder_candidates}
    evidence_table_labels = {table.label for table in evidence.tables}
    evidence_paste_zones = set(evidence.paste_zones)
    manifest_markers = {field.marker_text for field in manifest.fields if field.marker_text}

    missing_markers = evidence_markers - manifest_markers
    for m in missing_markers:
        # Ignore TableEnd as it's usually handled by the TableStart/loop field
        # and some technical markers like page breaks
        if "TableEnd:" not in m and not m.startswith("Section:"):
            errors.append(f"Structural marker '{m}' found in document but missing from manifest.")

    # 2. Hallucination check: Markers in manifest must exist in evidence
    hallucinated_markers = manifest_markers - evidence_markers
    for m in hallucinated_markers:
        if m in evidence_table_labels or m in evidence_paste_zones:
            continue
        # Sometimes LLMs clean up markers or strip characters, but we want exact match for rendering
        errors.append(f"Field marker '{m}' in manifest does not exist in document evidence.")

    # 3. Validate repeat blocks
    for field in manifest.fields:
        if field.field_type in ("table_loop", "repeat_block"):
             strategy = (field.injection_hints or field.render_locator or {}).get("strategy", "")
             if "TableStart:" not in field.marker_text and strategy != "replace_table_loop":
                  errors.append(f"Field '{field.fieldname}' is marked as {field.field_type} but marker '{field.marker_text}' is not a TableStart marker.")

    # 4. Instruction blocks should not be resume_fillable
    for field in manifest.fields:
        if "instruction" in field.meaning.lower() or "instruction" in field.fieldname.lower():
            if field.resume_fillable:
                warnings.append(f"Field '{field.fieldname}' looks like an instruction but is marked resume_fillable=True.")

    # 5. Check for duplicate fieldnames
    fieldnames = [f.fieldname for f in manifest.fields]
    seen = set()
    for name in fieldnames:
        if name in seen:
            errors.append(f"Manifest contains duplicate fieldname: '{name}'")
        seen.add(name)

    return errors, warnings
