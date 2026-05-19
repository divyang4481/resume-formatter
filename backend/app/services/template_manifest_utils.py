import json
from typing import Any, Dict


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
            "fields": [x for x in (raw.get("fields") or []) if isinstance(x, dict)],
            "instruction_blocks": raw.get("instruction_blocks") or [],
        }

    if isinstance(raw, dict) and "filled_template_manifest" in raw:
        inner = raw.get("filled_template_manifest") or {}
        return {
            "fields": [x for x in (inner.get("fields") or []) if isinstance(x, dict)],
            "instruction_blocks": inner.get("instruction_blocks") or [],
        }

    if isinstance(raw, dict) and "field_extraction_manifest" in raw:
        return normalize_template_manifest(raw.get("field_extraction_manifest"))

    if isinstance(raw, list):
        return {
            "fields": [x for x in raw if isinstance(x, dict)],
            "instruction_blocks": [],
        }

    return {"fields": [], "instruction_blocks": []}
