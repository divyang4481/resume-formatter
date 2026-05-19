from typing import Any, Dict, List, Optional

def default_value_for_field_type(field_type: str) -> Any:
    if field_type in ("array_simple", "array_complex", "table_loop"):
        return []
    if field_type == "complex_object":
        return {}
    if field_type == "paste_zone":
        return ""
    return ""

def marker_alias(marker_text: str) -> str | None:
    if not marker_text:
        return None

    marker = marker_text.strip()

    if marker.startswith("«") and marker.endswith("»"):
        return marker.strip("«»").strip()

    if marker.startswith("[") and marker.endswith("]"):
        return marker.strip("[]").strip().replace(" ", "_")

    return None

def build_render_context_from_template_fill_result(
    template_fill_result: Dict[str, Any],
    manifest_fields: List[Dict[str, Any]],
    filled_manifest_fields: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Converts strict mapping envelope into flat render context.

    Input:
      candidate_full_name: {
        value: "Divyang Panchasara",
        marker_text: "«CandidateFullName»",
        field_type: "scalar"
      }

    Output:
      candidate_full_name = "Divyang Panchasara"
      CandidateFullName = "Divyang Panchasara"
      candidatefullname = "Divyang Panchasara"
    """
    render_context: Dict[str, Any] = {}

    filled_by_name = {f.get("fieldname"): f for f in (filled_manifest_fields or []) if isinstance(f, dict) and f.get("fieldname")}

    manifest_by_field = {
        f.get("fieldname"): f
        for f in manifest_fields
        if isinstance(f, dict) and f.get("fieldname")
    }

    for fieldname, manifest_field in manifest_by_field.items():
        field_type = manifest_field.get("field_type", "scalar")
        marker_text = manifest_field.get("marker_text", "")

        entry = template_fill_result.get(fieldname)

        if isinstance(entry, dict):
            value = entry.get("value")
            # If missing, fallback to field_extraction_manifest.value
            if value is None and isinstance(entry.get("field_extraction_manifest"), dict):
                value = entry["field_extraction_manifest"].get("value")
        else:
            value = entry

        if value is None and isinstance(filled_by_name.get(fieldname), dict):
            value = (filled_by_name[fieldname].get("field_extraction_manifest") or {}).get("value")

        if value is None:
            value = default_value_for_field_type(field_type)

        render_context[fieldname] = value

        alias = marker_alias(marker_text)
        if alias:
            render_context[alias] = value
            render_context[alias.lower()] = value
            render_context["".join(ch for ch in alias.lower() if ch.isalnum())] = value

        render_context["".join(ch for ch in fieldname.lower() if ch.isalnum())] = value

    return render_context

def add_table_loop_aliases(
    render_context: Dict[str, Any],
    manifest_fields: List[Dict[str, Any]],
) -> None:
    for field in manifest_fields:
        fieldname = field.get("fieldname")
        marker = field.get("marker_text", "")
        value = render_context.get(fieldname)

        if not fieldname or not isinstance(value, list):
            continue

        if "TableStart:" in marker:
            loop_name = marker.replace("«TableStart:", "").replace("»", "").strip()

            # For Hays bCheckType loop, inner field is CheckType.
            # Generic rule: bSomething -> Something
            inner_field = loop_name[1:] if loop_name.startswith("b") else "value"

            if value and all(isinstance(x, dict) for x in value):
                # It is a complex array, keep it as list of dicts directly!
                render_context[loop_name] = value
            else:
                # It is a simple array of strings/scalars, wrap them!
                render_context[loop_name] = [
                    {inner_field: item}
                    for item in value
                ]

            if value:
                render_context[inner_field] = value[0]
