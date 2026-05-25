from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

class ResumeDataFormatter:
    """
    Expands array/complex/loop fields from harmonized resume data into
    render-ready flat dictionaries suitable for docxtpl rendering.
    """

    def expand_array_fields(
        self, resume_data: Dict[str, Any], field_manifest: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Expands array/complex/loop fields in resume_data into render-ready form.
        """
        expanded = dict(resume_data)

        # Build a quick lookup of field_type by fieldname
        if not field_manifest:
            fields_list = []
        elif isinstance(field_manifest, dict):
            fields_list = field_manifest.get("fields", []) or []
        else:
            fields_list = field_manifest
            
        manifest_map: Dict[str, Dict] = {}
        if fields_list:
            manifest_map = {
                entry["fieldname"]: entry
                for entry in fields_list
                if isinstance(entry, dict) and entry.get("fieldname")
            }

        for fieldname, value in list(expanded.items()):
            entry = manifest_map.get(fieldname, {})
            field_type = entry.get("field_type", "scalar")

            # --- instruction_block: clear from render context ---
            if field_type == "instruction_block" or fieldname.startswith(
                "_instruction_"
            ):
                expanded.pop(fieldname, None)
                continue

            # Unwrap dict-wrapped values (e.g. from template_fill_result containing "value" key)
            if isinstance(value, dict) and "value" in value:
                raw_val = value.get("value")
                if raw_val is None and isinstance(value.get("field_extraction_manifest"), dict):
                    raw_val = value["field_extraction_manifest"].get("value")
                value = raw_val
                expanded[fieldname] = value

            # --- scalar: list of strings handling ---
            if field_type == "scalar" and isinstance(value, list):
                # Join list items into a comma-separated string for scalar fields
                expanded[fieldname] = ", ".join([str(v) for v in value if v])
                value = expanded[fieldname] # update local value for subsequent checks if any

            # --- array_simple: list of strings ---
            if field_type == "array_simple" and isinstance(value, list):
                expanded[fieldname] = [str(v) for v in value if v]
                bullet_str = "\n".join(f"- {v}" for v in expanded[fieldname])
                expanded[f"{fieldname}_str"] = bullet_str
                logger.info(f"Formatted array_simple '{fieldname}' with {len(value)} items.")

            # --- array_complex: list of sub-field dicts ---
            elif field_type == "array_complex" and isinstance(value, list):
                expanded[fieldname] = value
                expanded[f"{fieldname}_str"] = self.format_array_complex_value(entry, value)
                logger.info(f"Formatted array_complex '{fieldname}' with {len(value)} items.")
                for i, item in enumerate(value, start=1):
                    if isinstance(item, dict):
                        for sub_key, sub_val in item.items():
                            expanded[f"{fieldname}_{i}_{sub_key}"] = sub_val

            # --- table_loop: list of dicts for docxtpl tr loops ---
            elif field_type == "table_loop" and isinstance(value, list):
                loop_variable = entry.get("loop_variable", fieldname)
                loop_items = [
                    item if isinstance(item, dict) else {"value": str(item)}
                    for item in value
                ]
                expanded[loop_variable] = loop_items
                if loop_variable != fieldname:
                    expanded[fieldname] = loop_items

        return expanded

    def format_array_complex_value(self, field_def: Dict[str, Any], value: Any) -> str:
        """
        Formats a complex array (list of dicts) into a multi-line string block 
        with specific text markers indicating formatting intentions.
        """
        if not isinstance(value, list):
            return ""
        sub_fields = ((field_def or {}).get("extract", {}) or {}).get("sub_fields", []) or []
        ordered_names = [sf.get("name") for sf in sub_fields if isinstance(sf, dict) and sf.get("name")]
        chunks: List[str] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            names = ordered_names or list(item.keys())
            header_parts: List[str] = []
            for name in names:
                v = item.get(name)
                if isinstance(v, list):
                    continue
                if v:
                    header_parts.append(str(v))
            if header_parts:
                chunks.append(" [:PIPE:] ".join(header_parts))
            for name in names:
                v = item.get(name)
                if isinstance(v, list):
                    for line in v:
                        if line:
                            chunks.append(f"[:L1:]{line}")
            chunks.append("[:BR:]")
        return "\n".join(c for c in chunks if c).strip()
