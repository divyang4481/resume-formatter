import json
from typing import Any, Dict, List
from app.services.field_mapping_nodes import canonicalize_field, get_fieldname


def _canonical_fields(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []

    output = []
    for item in items:
        if not isinstance(item, dict):
            continue

        field = canonicalize_field(item)
        if get_fieldname(field):
            output.append(field)

    return output


def normalize_template_manifest(raw: Any) -> Dict[str, Any]:
    """Normalize template manifest payload into {'fields': [...], 'instruction_blocks': [...]}."""
    if raw is None:
        return {"fields": [], "instruction_blocks": []}

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {"fields": [], "instruction_blocks": []}

    if isinstance(raw, dict) and "fields" in raw:
        return {
            "fields": _canonical_fields(raw.get("fields") or []),
            "instruction_blocks": raw.get("instruction_blocks") or [],
        }

    if isinstance(raw, dict) and "filled_template_manifest" in raw:
        inner = raw.get("filled_template_manifest") or {}
        return {
            "fields": _canonical_fields(inner.get("fields") or []),
            "instruction_blocks": inner.get("instruction_blocks") or [],
        }

    if isinstance(raw, dict) and "field_extraction_manifest" in raw:
        return normalize_template_manifest(raw.get("field_extraction_manifest"))

    if isinstance(raw, list):
        return {
            "fields": _canonical_fields(raw),
            "instruction_blocks": [],
        }

    return {"fields": [], "instruction_blocks": []}
