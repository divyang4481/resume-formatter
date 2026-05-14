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
    manifest_markers = {field.marker_text for field in manifest.fields if field.marker_text}

    missing_markers = evidence_markers - manifest_markers
    for m in missing_markers:
        # Ignore TableEnd as it's usually handled by the TableStart/loop field
        if "TableEnd:" not in m:
            errors.append(f"Structural marker '{m}' found in document but missing from manifest.")

    # 2. Validate repeat blocks
    for field in manifest.fields:
        if field.field_type in ("table_loop", "repeat_block"):
             if "TableStart:" not in field.marker_text and "TableEnd:" not in field.marker_text:
                  warnings.append(f"Field '{field.fieldname}' is marked as {field.field_type} but marker '{field.marker_text}' does not follow TableStart pattern.")

    # 3. Instruction blocks should not be resume_fillable
    for field in manifest.fields:
        if "instruction" in field.meaning.lower() or "instruction" in field.fieldname.lower():
            if field.resume_fillable:
                warnings.append(f"Field '{field.fieldname}' looks like an instruction but is marked resume_fillable=True.")

    # 4. Check for duplicate fieldnames
    fieldnames = [f.fieldname for f in manifest.fields]
    if len(fieldnames) != len(set(fieldnames)):
        errors.append("Manifest contains duplicate fieldnames.")

    return errors, warnings
