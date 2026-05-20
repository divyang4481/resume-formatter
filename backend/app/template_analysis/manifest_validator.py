from typing import List, Tuple
from .field_types import VALID_FIELD_TYPES, VALID_RENDER_STRATEGIES
from .models import TemplateEvidence, TemplateManifest


def validate_manifest_against_evidence(manifest: TemplateManifest, evidence: TemplateEvidence) -> Tuple[List[str], List[str]]:
    errors = []
    warnings = []
    evidence_markers = {ph.marker for ph in evidence.placeholder_candidates}
    evidence_table_labels = {table.label for table in evidence.tables}
    evidence_paste_zones = set(evidence.paste_zones)
    manifest_markers = {field.marker_text for field in manifest.fields if field.marker_text}

    for m in (evidence_markers - manifest_markers):
        if "TableEnd:" not in m and not m.startswith("Section:"):
            errors.append(f"Structural marker '{m}' found in document but missing from manifest.")
    for m in (manifest_markers - evidence_markers):
        if m not in evidence_table_labels and m not in evidence_paste_zones:
            errors.append(f"Field marker '{m}' in manifest does not exist in document evidence.")

    marker_section = {}
    for f in manifest.fields:
        if f.field_type not in VALID_FIELD_TYPES:
            errors.append(f"Invalid field_type '{f.field_type}' for field '{f.fieldname}'.")
        if f.field_type == 'repeat_block':
            errors.append(f"Field '{f.fieldname}' uses forbidden field_type repeat_block.")
        for loc_name, loc in (("render_locator", f.render_locator), ("injection_hints", f.injection_hints)):
            strategy = (loc or {}).get("strategy", "")
            if strategy not in VALID_RENDER_STRATEGIES:
                errors.append(f"Field '{f.fieldname}' has invalid {loc_name}.strategy '{strategy}'.")
            if strategy == "repeat_block":
                errors.append(f"Field '{f.fieldname}' uses forbidden strategy repeat_block.")

        if f.field_type == "array_complex":
            if not f.sub_fields:
                errors.append(f"array_complex field '{f.fieldname}' must have at least one sub_field.")
            if (f.render_locator or {}).get("strategy") != "replace_complex_block":
                warnings.append(f"array_complex field '{f.fieldname}' should use replace_complex_block strategy.")
        if f.field_type == "table_loop":
            strategy = (f.injection_hints or f.render_locator or {}).get("strategy", "")
            if "TableStart:" not in f.marker_text and strategy != "replace_table_loop":
                errors.append(f"table_loop field '{f.fieldname}' must have TableStart marker or replace_table_loop strategy.")

        sec = ((f.render_locator or {}).get("heading") or (f.context or {}).get("section_heading") or "")
        k = (sec, f.marker_text)
        if f.marker_text:
            if k in marker_section:
                warnings.append(f"Duplicate top-level marker '{f.marker_text}' under section '{sec}'.")
            marker_section[k] = f.fieldname

    top_keys = {( ((f.render_locator or {}).get("heading") or (f.context or {}).get("section_heading") or ""), f.marker_text) for f in manifest.fields}
    for f in manifest.fields:
        if f.field_type == "array_complex":
            sec = ((f.render_locator or {}).get("heading") or (f.context or {}).get("section_heading") or "")
            for sf in f.sub_fields:
                if (sec, sf.marker_text) in top_keys:
                    warnings.append(f"Child marker '{sf.marker_text}' for '{f.fieldname}' also exists as top-level field in same section.")

    return errors, warnings
