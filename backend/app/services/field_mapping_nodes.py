from typing import Any, Dict, List, Optional
from app.services.field_extraction_manifest_utils import make_empty_fem


DEFAULT_FIELD_NODE_BATCH_SIZE = 6


def get_fieldname(field: Dict[str, Any]) -> str:
    if not isinstance(field, dict):
        return ""
    return (
        field.get("fieldname")
        or field.get("field_name")
        or field.get("name")
        or field.get("id")
        or ""
    )


def canonicalize_field(field: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(field, dict):
        return {}

    out = dict(field)
    fname = get_fieldname(out)
    if fname:
        out["fieldname"] = fname

    out.pop("field_name", None)
    return out


def field_to_mapping_node(field: Dict[str, Any]) -> Dict[str, Any]:
    field = canonicalize_field(field)
    fieldname = get_fieldname(field)

    return {
        "node_id": fieldname,
        "fieldname": fieldname,
        "field_type": field.get("field_type", "scalar"),
        "required": field.get("required", False),
        "marker_text": field.get("marker_text", ""),
        "meaning": field.get("meaning", ""),
        "source_hints": field.get("source_hints", ""),
        "render_locator": field.get("render_locator", {}),
        "original_field": field,
        "field_extraction_manifest": field.get("field_extraction_manifest"),
    }


def fields_to_mapping_nodes(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nodes = []
    for field in fields or []:
        if not isinstance(field, dict):
            continue

        field = canonicalize_field(field)
        if not get_fieldname(field):
            continue

        if field.get("field_type") == "instruction_block":
            continue

        nodes.append(field_to_mapping_node(field))

    return nodes


def batch_field_nodes(
    nodes: List[Dict[str, Any]],
    batch_size: int = DEFAULT_FIELD_NODE_BATCH_SIZE,
) -> List[List[Dict[str, Any]]]:
    if batch_size <= 0:
        batch_size = DEFAULT_FIELD_NODE_BATCH_SIZE
    return [nodes[i:i + batch_size] for i in range(0, len(nodes), batch_size)]


def compact_node_for_llm(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "node_id": node.get("node_id") or node.get("fieldname"),
        "fieldname": node.get("fieldname"),
        "field_type": node.get("field_type", "scalar"),
        "required": node.get("required", False),
        "meaning": node.get("meaning", ""),
        "source_hints": node.get("source_hints", ""),
        "marker_text": node.get("marker_text", ""),
        "render_locator": node.get("render_locator", {}),
    }


def canonicalize_mapped_node(node: Dict[str, Any]) -> Dict[str, Any]:
    fieldname = (
        node.get("fieldname")
        or node.get("field_name")
        or node.get("node_id")
        or node.get("id")
        or ""
    )
    node_id = node.get("node_id") or fieldname

    return {
        "node_id": node_id,
        "fieldname": fieldname,
        "field_extraction_manifest": node.get("field_extraction_manifest"),
    }


def extract_mapped_nodes_from_response(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, dict):
        if isinstance(parsed.get("nodes"), list):
            return [canonicalize_mapped_node(n) for n in parsed["nodes"]]

        # Backward compatibility for filled_template_manifest wrapper
        if "filled_template_manifest" in parsed:
            inner = parsed["filled_template_manifest"]
            if isinstance(inner, dict) and isinstance(inner.get("fields"), list):
                return [
                    canonicalize_mapped_node({
                        "node_id": get_fieldname(f),
                        "fieldname": get_fieldname(f),
                        "field_extraction_manifest": f.get("field_extraction_manifest"),
                    })
                    for f in inner["fields"]
                    if isinstance(f, dict)
                ]

        # Backward compatibility for old field response.
        if isinstance(parsed.get("fields"), list):
            return [
                canonicalize_mapped_node({
                    "node_id": get_fieldname(f),
                    "fieldname": get_fieldname(f),
                    "field_extraction_manifest": f.get("field_extraction_manifest"),
                })
                for f in parsed["fields"]
                if isinstance(f, dict)
            ]

        # Backward compatibility for old template_fill_result response.
        tfr = parsed.get("template_fill_result")
        if isinstance(tfr, dict):
            output = []
            for fieldname, entry in tfr.items():
                if not isinstance(entry, dict):
                    entry = {"value": entry}

                fem = entry.get("field_extraction_manifest")
                if not isinstance(fem, dict):
                    fem = {
                        "value_type": "scalar",
                        "value": entry.get("value"),
                        "confidence": entry.get("confidence", 0.0),
                        "status": entry.get("status", "not_found"),
                        "reason": entry.get("reason", "Recovered from template_fill_result."),
                        "source": entry.get("source", {"resume_section": None, "evidence": None}),
                    }

                output.append(canonicalize_mapped_node({
                    "node_id": fieldname,
                    "fieldname": fieldname,
                    "field_extraction_manifest": fem,
                }))
            return output

    if isinstance(parsed, list):
        return [canonicalize_mapped_node(n) for n in parsed if isinstance(n, dict)]

    return []


def make_empty_fem_for_node(node: Dict[str, Any]) -> Dict[str, Any]:
    return make_empty_fem(
        node.get("field_type", "scalar"),
        node.get("fieldname") or node.get("node_id") or "unknown_field",
    )


def make_fallback_mapped_node(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "node_id": node.get("node_id"),
        "fieldname": node.get("fieldname"),
        "field_extraction_manifest": make_empty_fem_for_node(node),
    }


def synthesize_filled_fields_from_nodes(
    original_nodes: List[Dict[str, Any]],
    mapped_nodes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    mapped_by_node_id = {}

    for mapped in mapped_nodes or []:
        node_id = mapped.get("node_id") or mapped.get("fieldname")
        if not node_id:
            continue
        if node_id in mapped_by_node_id:
            # Keep first result for deterministic behavior.
            continue
        mapped_by_node_id[node_id] = mapped

    filled_fields = []

    for node in original_nodes:
        node_id = node.get("node_id")
        original_field = canonicalize_field(node.get("original_field") or {})
        mapped = mapped_by_node_id.get(node_id) or {}

        fem = mapped.get("field_extraction_manifest")
        if not isinstance(fem, dict):
            fem = make_empty_fem(
                node.get("field_type", "scalar"),
                node.get("fieldname", node_id),
            )

        final_field = dict(original_field)
        final_field["fieldname"] = node.get("fieldname", node_id)
        final_field["field_extraction_manifest"] = fem
        filled_fields.append(final_field)

    return filled_fields
