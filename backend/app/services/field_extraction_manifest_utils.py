from typing import Any, Dict

def make_empty_fem(field_type: str, fieldname: str) -> Dict[str, Any]:
    """Return an empty field_extraction_manifest for a field with no value."""
    if field_type in ("array_simple", "array_complex", "table_loop"):
        empty_val: Any = []
    elif field_type == "complex_object":
        empty_val = {}
    elif field_type == "paste_zone":
        empty_val = None
    else:
        empty_val = None

    return {
        "value_type": (
            "array" if field_type in ("array_simple", "table_loop")
            else "array_complex" if field_type == "array_complex"
            else "complex_object" if field_type == "complex_object"
            else "rich_text" if field_type in ("rich_text", "paste_zone")
            else "scalar"
        ),
        "value": empty_val,
        "confidence": 0.0,
        "status": "not_found",
        "reason": f"Field '{fieldname}' was not found in the candidate resume.",
        "source": {"resume_section": None, "evidence": None},
    }
